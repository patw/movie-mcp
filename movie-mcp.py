import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from fastmcp import FastMCP
from typing import List, Optional, Union, Dict, Any
import json
import sys

# Check if a MongoDB URI was passed as a command-line argument
if len(sys.argv) > 1:
    MONGO_URI = sys.argv[1]
else:
    print("Please provide the MongoDB URI as a command-line argument.")
    sys.exit(1)

# --- MongoDB Connection ---
# It's good practice to use environment variables for sensitive info like URIs
# For this example, we'll use a default. Replace with your MONGO_URI if needed.
DATABASE_NAME = "sample_mflix"
COLLECTION_NAME = "movies"

try:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    movies_collection = db[COLLECTION_NAME]
    print("Successfully connected to MongoDB and the 'sample_mflix.movies' collection.")
except Exception as e:
    print(f"Error connecting to MongoDB or accessing collection: {e}")
    print("Please ensure MongoDB is running and accessible, and the 'sample_mflix' database with 'movies' collection exists.")
    # Exit if connection is critical for the module to load
    raise SystemExit(f"MongoDB connection failed: {e}")


mcp = FastMCP("Movie Database Wizard")

# --- Constants and Mappings ---
RATING_FIELD_MAP = {
    "imdb": "imdb.rating",
    "metacritic": "metacritic",
    "tomatoes_viewer": "tomatoes.viewer.rating",
    "tomatoes_critic": "tomatoes.critic.rating",
    # Adding fields for sorting by popularity/votes if desired
    "imdb_votes": "imdb.votes",
    "tomatoes_viewer_num_reviews": "tomatoes.viewer.numReviews",
    "tomatoes_critic_num_reviews": "tomatoes.critic.numReviews",
}

DEFAULT_PROJECTION_FIELDS = ["title", "year", "plot", "imdb.rating", "genres"]

# This is terrible and was needed because Claude was not sending lists properly
def _parse_stringified_list_arg(arg: Optional[Union[List[str], str]]) -> Optional[List[str]]:
    if arg is None:
        return None
    if isinstance(arg, list):
        # Ensure all items in the list are strings and filter out any None items
        return [str(item) for item in arg if item is not None]

    if isinstance(arg, str):
        # Handle empty or whitespace-only strings by returning None (ignoring filter)
        if not arg.strip(): 
            print(f"Warning: Argument '{arg}' is an empty or whitespace string. Ignoring this filter argument.")
            return None
        try:
            # Attempt to parse as JSON, assuming it might be a stringified list
            parsed_arg = json.loads(arg)
            if isinstance(parsed_arg, list):
                # Ensure all items are strings and filter out any None items
                return [str(item) for item in parsed_arg if item is not None]
            else:
                # It's valid JSON, but not a list (e.g., a JSON object string or number string).
                # This is ambiguous for list-expecting fields like actors/genres.
                # Returning None means this filter criteria will be ignored, which is safer.
                print(f"Warning: Argument '{arg}' was valid JSON but not a list of strings. Ignoring this filter argument.")
                return None
        except json.JSONDecodeError:
            # Not valid JSON. Assume it's a single string value intended as a list of one.
            # e.g., actors="Bill Murray" or genres="Comedy"
            # This is the key fix for the user's reported issue.
            # print(f"Info: Argument '{arg}' was not a JSON list. Treating as a single item list: [{arg}].") # Optional: uncomment for debugging
            return [arg] # Treat the non-JSON string as a single item in a list
    
    # If arg is not None, not a list, and not a string (e.g., an integer passed directly for a list field)
    # This might happen if the calling framework doesn't strictly enforce type hints for complex types.
    print(f"Warning: Argument '{arg}' of type {type(arg)} is not a list or string suitable for list conversion. Ignoring this filter argument.")
    return None

# --- Helper Function to Build MongoDB Query ---
def _build_movie_query(
    title: Optional[str] = None,
    genres: Optional[List[str]] = None,
    actors: Optional[List[str]] = None,
    directors: Optional[List[str]] = None,
    writers: Optional[List[str]] = None,
    year: Optional[int] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_imdb_rating: Optional[float] = None,
    min_metacritic_rating: Optional[int] = None,
    min_tomatoes_viewer_rating: Optional[float] = None,
    min_tomatoes_critic_rating: Optional[float] = None,
    rated_mpaa: Optional[str] = None  # MPAA rating like "R", "PG-13"
) -> Dict[str, Any]:
    """
    Constructs a MongoDB query dictionary based on provided filter criteria.
    """
    query: Dict[str, Any] = {}
    
    if title:
        query["title"] = {"$regex": title, "$options": "i"}  # Case-insensitive partial match
    
    if genres:
        # Movie must have ALL specified genres
        query["genres"] = {"$all": genres} 

    # For actors, directors, writers: match if all names appear (case-insensitive, partial match)
    # in their respective array fields (cast, directors, writers).
    # E.g., actors=["De Niro", "Pesci"] means movies with both De Niro AND Pesci.
    # Each name is matched as a regex within the elements of the field.
    for field_name, names_list in [("cast", actors), ("directors", directors), ("writers", writers)]:
        if names_list:
            if not query.get("$and"):
                query["$and"] = []
            for name in names_list:
                # This query part means: the field (e.g., "cast") must contain an element
                # that matches the regex `name`. If multiple names are provided, all such conditions must be true.
                query["$and"].append({field_name: {"$regex": name, "$options": "i"}})

    if year is not None:
        query["year"] = year
    elif start_year is not None or end_year is not None: # Handle year ranges
        year_query_conditions = {}
        if start_year is not None:
            year_query_conditions["$gte"] = start_year
        if end_year is not None:
            year_query_conditions["$lte"] = end_year
        if year_query_conditions:
            query["year"] = year_query_conditions

    # Minimum rating filters
    if min_imdb_rating is not None:
        query["imdb.rating"] = {"$gte": min_imdb_rating, "$exists": True}
    if min_metacritic_rating is not None:
        query["metacritic"] = {"$gte": min_metacritic_rating, "$exists": True}
    if min_tomatoes_viewer_rating is not None:
        query["tomatoes.viewer.rating"] = {"$gte": min_tomatoes_viewer_rating, "$exists": True}
    if min_tomatoes_critic_rating is not None:
        query["tomatoes.critic.rating"] = {"$gte": min_tomatoes_critic_rating, "$exists": True}

    if rated_mpaa:
        # Case-insensitive exact match for MPAA rating (field name is 'rated')
        query["rated"] = {"$regex": f"^{rated_mpaa}$", "$options": "i"} 

    return query

# --- MCP Tools ---

@mcp.tool
def find_movies(
    title: Optional[str] = None,
    genres: Optional[Union[List[str], str]] = None, # Modified type hint
    actors: Optional[Union[List[str], str]] = None, # Modified type hint
    directors: Optional[Union[List[str], str]] = None, # Modified type hint
    writers: Optional[Union[List[str], str]] = None, # Modified type hint
    year: Optional[int] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_imdb_rating: Optional[float] = None,
    min_metacritic_rating: Optional[int] = None,
    min_tomatoes_viewer_rating: Optional[float] = None,
    min_tomatoes_critic_rating: Optional[float] = None,
    rated_mpaa: Optional[str] = None,
    sort_by: Optional[str] = "imdb.rating", # Default sort: IMDb rating
    sort_order_asc: bool = False, # Default: False (Descending, e.g., highest rated first)
    limit: int = 10, # Default: 10 results
    projection_fields: Optional[List[str]] = None # Fields to return
) -> List[Dict[str, Any]]:
    """
    Finds movies based on a variety of criteria, with options for sorting and limiting results.
    Args:
        title: Movie title (case-insensitive partial match).
        genres: List of genres; movie must match all specified genres.
        actors: List of actor names; movie must feature all specified actors (case-insensitive partial match for each name within the cast list).
        directors: List of director names; movie must be directed by all specified directors (case-insensitive partial match for each name).
        writers: List of writer names; movie must include all specified writers (case-insensitive partial match for each name).
        year: Exact release year.
        start_year: Start of a release year range (inclusive).
        end_year: End of a release year range (inclusive).
        min_imdb_rating: Minimum IMDb rating (e.g., 7.5).
        min_metacritic_rating: Minimum Metacritic score (e.g., 70).
        min_tomatoes_viewer_rating: Minimum Rotten Tomatoes viewer rating (e.g., 3.5).
        min_tomatoes_critic_rating: Minimum Rotten Tomatoes critic rating (e.g., 7.0).
        rated_mpaa: MPAA rating (e.g., "R", "PG-13"). Case-insensitive exact match.
        sort_by: Field to sort results by (e.g., "imdb.rating", "year", "title", or short keys: "imdb", "metacritic"). Defaults to 'imdb.rating'.
        sort_order_asc: Sort order. False for descending (default, e.g., highest rated first), True for ascending (e.g., lowest rated first).
        limit: Maximum number of results to return. Defaults to 10. Use 0 for no limit.
        projection_fields: Specific fields to return for each movie (e.g., ["title", "year"]). Defaults to a standard set (title, year, plot, imdb.rating, genres).
    Returns:
        A list of movie documents (or specified fields). Returns an empty list if no movies match the criteria or an error occurs.
    """

    # Parse list-like arguments
    parsed_genres = _parse_stringified_list_arg(genres)
    parsed_actors = _parse_stringified_list_arg(actors)
    parsed_directors = _parse_stringified_list_arg(directors)
    parsed_writers = _parse_stringified_list_arg(writers)

    query = _build_movie_query(
        title, 
        genres=parsed_genres, # Use parsed value
        actors=parsed_actors, # Use parsed value
        directors=parsed_directors, # Use parsed value
        writers=parsed_writers, # Use parsed value
        year=year, start_year=start_year, end_year=end_year,
        min_imdb_rating=min_imdb_rating, min_metacritic_rating=min_metacritic_rating, 
        min_tomatoes_viewer_rating=min_tomatoes_viewer_rating, 
        min_tomatoes_critic_rating=min_tomatoes_critic_rating,
        rated_mpaa=rated_mpaa
    )

    # Determine projection (which fields to return)
    final_projection: Optional[Dict[str, int]] = None
    if projection_fields: # User specified fields
        final_projection = {field: 1 for field in projection_fields}
    else: # Default fields
        final_projection = {field: 1 for field in DEFAULT_PROJECTION_FIELDS}
    
    # Ensure _id is not returned unless explicitly asked for
    if final_projection:
        # If projection_fields is None (using default), it won't contain "_id"
        # If projection_fields is provided, check if "_id" is in it
        if "_id" not in (projection_fields or []): 
             final_projection["_id"] = 0

    try:
        cursor = movies_collection.find(query, final_projection)

        if sort_by:
            # Map short keys (e.g., "imdb") to actual database field paths
            db_sort_field = RATING_FIELD_MAP.get(sort_by, sort_by)
            mongo_sort_order = DESCENDING if not sort_order_asc else ASCENDING
            
            # Add $exists check to sort field if it's a rating to ensure meaningful sort
            # This is implicitly handled by MongoDB, but can be made explicit if issues arise
            # with how nulls/missing fields are sorted.
            # For example, if sorting by "imdb.rating", we might add query[db_sort_field] = {"$exists": True}
            # For now, we rely on MongoDB's default behavior.
            cursor = cursor.sort(db_sort_field, mongo_sort_order)

        if limit > 0: # PyMongo's limit(0) means no limit.
            cursor = cursor.limit(limit)
        # If limit is 0, no limit is applied by default by PyMongo if .limit(0) is called.
        # So, we can simply pass it or conditionally call limit.

        return list(cursor)
    except Exception as e:
        print(f"Error during find_movies query execution: {e}")
        return []


@mcp.tool
def count_movies(
    title: Optional[str] = None,
    genres: Optional[Union[List[str], str]] = None, # Modified type hint
    actors: Optional[Union[List[str], str]] = None, # Modified type hint
    directors: Optional[Union[List[str], str]] = None, # Modified type hint
    writers: Optional[Union[List[str], str]] = None, # Modified type hint
    year: Optional[int] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_imdb_rating: Optional[float] = None,
    min_metacritic_rating: Optional[int] = None,
    min_tomatoes_viewer_rating: Optional[float] = None,
    min_tomatoes_critic_rating: Optional[float] = None,
    rated_mpaa: Optional[str] = None
) -> int:
    """
    Counts movies based on the specified criteria.
    (Arguments are the same as the filtering arguments for the find_movies tool)
    Returns:
        The number of movies matching the criteria. Returns 0 if an error occurs.
    """

    # Parse list-like arguments
    parsed_genres = _parse_stringified_list_arg(genres)
    parsed_actors = _parse_stringified_list_arg(actors)
    parsed_directors = _parse_stringified_list_arg(directors)
    parsed_writers = _parse_stringified_list_arg(writers)

    query = _build_movie_query(
        title, parsed_genres, parsed_actors, parsed_directors, parsed_writers, year, start_year, end_year,
        min_imdb_rating, min_metacritic_rating, min_tomatoes_viewer_rating, min_tomatoes_critic_rating,
        rated_mpaa
    )
    try:
        return movies_collection.count_documents(query)
    except Exception as e:
        print(f"Error during count_movies query execution: {e}")
        return 0

@mcp.tool
def get_average_rating(
    rating_field_key: str, # Key like "imdb", "metacritic"
    genres: Optional[Union[List[str], str]] = None, # Modified type hint
    actors: Optional[Union[List[str], str]] = None, # Modified type hint
    directors: Optional[Union[List[str], str]] = None, # Modified type hint
    writers: Optional[Union[List[str], str]] = None, # Modified type hint
    year: Optional[int] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Calculates the average rating for movies matching the criteria, for a specific rating type.
    Args:
        rating_field_key: The key for the rating source (e.g., "imdb", "metacritic", "tomatoes_viewer", "tomatoes_critic").
        (Other filtering arguments are similar to those in find_movies/count_movies, excluding title, min_ratings, and rated_mpaa as they are less common for broad average calculations).
    Returns:
        A dictionary containing 'average_rating' (float, rounded to 2 decimal places) and 'movie_count' (int). 
        Returns None if the rating_field_key is invalid, or a dict with None average_rating and 0 count if no movies match or an error occurs.
    """
    db_rating_field = RATING_FIELD_MAP.get(rating_field_key)
    if not db_rating_field:
        print(f"Invalid rating_field_key provided to get_average_rating: {rating_field_key}")
        return None
    
    # Parse list-like arguments
    parsed_genres = _parse_stringified_list_arg(genres)
    parsed_actors = _parse_stringified_list_arg(actors)
    parsed_directors = _parse_stringified_list_arg(directors)
    parsed_writers = _parse_stringified_list_arg(writers)

    # Build the match query using a subset of filters relevant for averaging
    match_query = _build_movie_query(
        genres=parsed_genres, actors=parsed_actors, directors=parsed_directors, writers=parsed_writers,
        year=year, start_year=start_year, end_year=end_year
    )
    
    # Crucially, ensure the rating field exists and is a number for the $avg operator
    match_query[db_rating_field] = {"$exists": True, "$type": "number"} 
    # "$type: 'number'" is an alias in MongoDB that matches BSON types: double, int, long, decimal.

    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": None, # Group all matched documents together
            "averageRating": {"$avg": f"${db_rating_field}"},
            "movieCount": {"$sum": 1} # Count how many movies contributed to the average
        }}
    ]
    
    try:
        result = list(movies_collection.aggregate(pipeline))
        if result and result[0]["movieCount"] > 0:
            avg_rating = result[0]["averageRating"]
            return {
                "average_rating": round(avg_rating, 2) if avg_rating is not None else None,
                "movie_count": result[0]["movieCount"]
            }
        # No movies matched criteria or had the specified rating field as a number
        return {"average_rating": None, "movie_count": 0}
    except Exception as e:
        print(f"Error during get_average_rating aggregation: {e}")
        # Return a clear "no result" state in case of error
        return {"average_rating": None, "movie_count": 0, "error": str(e)}


if __name__ == "__main__":
    print("FastMCP Movie Database Server starting...")
    
    # --- Sanity Checks / Manual Tool Testing (Optional) ---
    # These mimic how an LLM might call the tools.
    # print("\n--- Example Tool Calls (for testing) ---")
    
    # 1. "What movies is Bill Murray In?" (show top 3, title and year)
    # bill_murray_movies = find_movies(actors=["Bill Murray"], limit=3, projection_fields=["title", "year", "cast"])
    # print(f"\nBill Murray movies (top 3): {bill_murray_movies}")

    # 2. "How many Comedy movies were there in 1985?"
    # comedy_count_1985 = count_movies(genres=["Comedy"], year=1985)
    # print(f"\nNumber of Comedy movies in 1985: {comedy_count_1985}")

    # 3. "What's the 2 highest rated movies from 1988?" (using IMDb)
    # top_1988_movies = find_movies(year=1988, sort_by="imdb", sort_order_asc=False, limit=2, projection_fields=["title", "year", "imdb.rating"])
    # print(f"\nTop 2 IMDb-rated movies from 1988: {top_1988_movies}")

    # 4. "What's the 2 lowest rated movies of the 90's?" (using IMDb)
    # lowest_90s_movies = find_movies(start_year=1990, end_year=1999, sort_by="imdb", sort_order_asc=True, limit=2, projection_fields=["title", "year", "imdb.rating"])
    # print(f"\nLowest 2 IMDb-rated movies from 1990-1999: {lowest_90s_movies}")

    # 5. "Do Bill Murray Movies have better ratings than Kevin Bacon Movies?" (IMDb)
    # avg_rating_bill = get_average_rating(rating_field_key="imdb", actors=["Bill Murray"])
    # avg_rating_kevin = get_average_rating(rating_field_key="imdb", actors=["Kevin Bacon"])
    # print(f"\nAverage IMDb rating for Bill Murray movies: {avg_rating_bill}")
    # print(f"Average IMDb rating for Kevin Bacon movies: {avg_rating_kevin}")
    # if avg_rating_bill and avg_rating_kevin and avg_rating_bill.get("average_rating") is not None and avg_rating_kevin.get("average_rating") is not None:
    #     if avg_rating_bill["average_rating"] > avg_rating_kevin["average_rating"]:
    #         print("Bill Murray movies tend to have higher IMDb ratings.")
    #     elif avg_rating_bill["average_rating"] < avg_rating_kevin["average_rating"]:
    #         print("Kevin Bacon movies tend to have higher IMDb ratings.")
    #     else:
    #         print("Bill Murray and Kevin Bacon movies have similar average IMDb ratings (based on available data).")
    # else:
    #     print("Could not compare Bill Murray and Kevin Bacon movie ratings.")
    # print("--- End Example Tool Calls ---")
    
    mcp.run()