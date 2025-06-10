# MongoDB Movie Database FastMCP Tools

This project provides a Python script that exposes a set of powerful tools for querying and analyzing a MongoDB movie database (specifically the `sample_mflix` dataset) using the `fastmcp` library. These tools are designed to be easily integrated with large language models (LLMs), AI agents, or any other system requiring structured, programmatic access to movie data.

## Table of Contents

* [Features](#features)
* [Prerequisites](#prerequisites)
* [MongoDB Setup](#mongodb-setup)
* [Installation](#installation)
* [Usage](#usage)
* [FastMCP Tools](#fastmcp-tools)
* [`find_movies`](#find_movies)
* [`count_movies`](#count_movies)
* [`get_average_rating`](#get_average_rating)
* [Contributing](#contributing)
* [License](#license)

## Features

* **Comprehensive Movie Search:** Find movies by title, genre, actors, directors, writers, year, or various rating thresholds.
* **Flexible Data Retrieval:** Specify fields to return (`projection_fields`) and control sorting (`sort_by`, `sort_order_asc`).
* **Movie Counting:** Quickly count movies matching specific criteria.
* **Average Rating Calculation:** Compute average IMDb, Metacritic, or Rotten Tomatoes ratings for filtered movie sets.
* **LLM-Friendly:** Designed with `fastmcp` to create a robust, self-documenting API easily consumable by LLMs. Includes special handling for stringified list arguments, addressing common LLM output formats.
* **Robust MongoDB Integration:** Utilizes `pymongo` for efficient and reliable database operations.

## Prerequisites

Before running this project, ensure you have the following:

* **Python 3.7+**: [Download Python](https://www.python.org/downloads/)
* **MongoDB Instance**: A running MongoDB instance (local or cloud-hosted like MongoDB Atlas).
* **`sample_mflix` Dataset**: The `sample_mflix` database and its `movies` collection must be loaded into your MongoDB instance.

### Optionally

* Claude Desktop

```
{
  "mcpServers": {
    "Movie Database": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp, pymongo",
        "fastmcp",
        "run",
        "<path to>/movie-mcp/movie-mcp.py",
        "<mongo connection string URI>"
      ]
    }
  }
}
```

## MongoDB Setup

This application connects to the `sample_mflix` database and specifically the `movies` collection.

**If you're using MongoDB Atlas:**
1. Log in to your [MongoDB Atlas account](https://cloud.mongodb.com/).
2. Navigate to your cluster.
3. Go to the "..." (usually `Data` or `Load Sample Data`) tab.
4. Click "Load Sample Dataset" and select `sample_mflix`. This will automatically import the necessary data.

**If you're using a local MongoDB instance:**
You can download the `sample_mflix` dataset from MongoDB's official resources (e.g., as part of the MongoDB University course materials or directly from their sample data repositories) and import it using `mongoimport`.

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```
(Replace `your-username/your-repo-name` with your actual repository details.)

2. **Create a virtual environment (recommended):**
```bash
python -m venv venv
source venv/bin/activate # On Windows: `venv\Scripts\activate`
```

3. **Install dependencies:**
Create a `requirements.txt` file in your project root with the following content:
```
pymongo
fastmcp
```
Then install them:
```bash
pip install -r requirements.txt
```

## Usage

The script expects the MongoDB connection URI as a command-line argument.

1. **Run the script:**
```bash
python movie_tools.py "mongodb://localhost:27017/"
```
Or, if using a MongoDB Atlas connection string:
```bash
python movie_tools.py "mongodb+srv://:@/?retryWrites=true&w=majority"
```
Replace ``, ``, ``, and `` with your actual MongoDB Atlas credentials and cluster details.

2. **FastMCP Server:**
Once running, the script will start a `fastmcp` server. This server exposes the defined tools (e.g., `find_movies`, `count_movies`) over a local HTTP endpoint (by default `http://127.0.0.1:8000/tools`). You can then interact with these tools programmatically, typically from an LLM agent or another Python script.

Example of how an LLM or another program might call these tools (conceptually):
```python
# This is pseudo-code representing how an LLM agent might interact
# In a real scenario, you'd use a client library for fastmcp or direct HTTP requests.

# Example: Find movies by Bill Murray
tool_call = {
"tool_name": "find_movies",
"args": {
"actors": ["Bill Murray"],
"limit": 5,
"projection_fields": ["title", "year", "imdb.rating"]
}
}
# result = make_tool_call(tool_call)
# print(result)

# Example: Count romantic comedies from the 90s
tool_call = {
"tool_name": "count_movies",
"args": {
"genres": ["Comedy", "Romance"],
"start_year": 1990,
"end_year": 1999
}
}
# result = make_tool_call(tool_call)
# print(result)
```

## FastMCP Tools

This section details the functions exposed as tools by `fastmcp`.

### `find_movies`

Finds movies based on a variety of criteria, with options for sorting and limiting results.

```python
def find_movies(
title: Optional[str] = None,
genres: Optional[Union[List[str], str]] = None,
actors: Optional[Union[List[str], str]] = None,
directors: Optional[Union[List[str], str]] = None,
writers: Optional[Union[List[str], str]] = None,
year: Optional[int] = None,
start_year: Optional[int] = None,
end_year: Optional[int] = None,
min_imdb_rating: Optional[float] = None,
min_metacritic_rating: Optional[int] = None,
min_tomatoes_viewer_rating: Optional[float] = None,
min_tomatoes_critic_rating: Optional[float] = None,
rated_mpaa: Optional[str] = None,
sort_by: Optional[str] = "imdb.rating",
sort_order_asc: bool = False,
limit: int = 10,
projection_fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
```

**Args:**

* `title` (str, optional): Movie title (case-insensitive partial match).
* `genres` (List[str] or str, optional): List of genres; movie must match all specified genres. If a single string is passed (e.g., "Comedy"), it's treated as a list of one.
* `actors` (List[str] or str, optional): List of actor names; movie must feature all specified actors (case-insensitive partial match for each name within the cast list). If a single string is passed, it's treated as a list of one.
* `directors` (List[str] or str, optional): List of director names; movie must be directed by all specified directors (case-insensitive partial match for each name). If a single string is passed, it's treated as a list of one.
* `writers` (List[str] or str, optional): List of writer names; movie must include all specified writers (case-insensitive partial match for each name). If a single string is passed, it's treated as a list of one.
* `year` (int, optional): Exact release year.
* `start_year` (int, optional): Start of a release year range (inclusive).
* `end_year` (int, optional): End of a release year range (inclusive).
* `min_imdb_rating` (float, optional): Minimum IMDb rating (e.g., 7.5).
* `min_metacritic_rating` (int, optional): Minimum Metacritic score (e.g., 70).
* `min_tomatoes_viewer_rating` (float, optional): Minimum Rotten Tomatoes viewer rating (e.g., 3.5).
* `min_tomatoes_critic_rating` (float, optional): Minimum Rotten Tomatoes critic rating (e.g., 7.0).
* `rated_mpaa` (str, optional): MPAA rating (e.g., "R", "PG-13"). Case-insensitive exact match.
* `sort_by` (str, optional): Field to sort results by. Can be a MongoDB path (e.g., "imdb.rating", "year", "title") or a short key ("imdb", "metacritic", "tomatoes_viewer", "tomatoes_critic", "imdb_votes", "tomatoes_viewer_num_reviews", "tomatoes_critic_num_reviews"). Defaults to 'imdb.rating'.
* `sort_order_asc` (bool, optional): Sort order. `False` for descending (default, e.g., highest rated first), `True` for ascending (e.g., lowest rated first).
* `limit` (int, optional): Maximum number of results to return. Defaults to 10. Use `0` for no limit.
* `projection_fields` (List[str], optional): Specific fields to return for each movie (e.g., `["title", "year"]`). Defaults to a standard set (`title`, `year`, `plot`, `imdb.rating`, `genres`).

**Returns:**

* `List[Dict[str, Any]]`: A list of movie documents (or specified fields). Returns an empty list if no movies match the criteria or an error occurs.

### `count_movies`

Counts movies based on the specified criteria.

```python
def count_movies(
title: Optional[str] = None,
genres: Optional[Union[List[str], str]] = None,
actors: Optional[Union[List[str], str]] = None,
directors: Optional[Union[List[str], str]] = None,
writers: Optional[Union[List[str], str]] = None,
year: Optional[int] = None,
start_year: Optional[int] = None,
end_year: Optional[int] = None,
min_imdb_rating: Optional[float] = None,
min_metacritic_rating: Optional[int] = None,
min_tomatoes_viewer_rating: Optional[float] = None,
min_tomatoes_critic_rating: Optional[float] = None,
rated_mpaa: Optional[str] = None
) -> int:
```

**Args:**
(Same as the filtering arguments for the `find_movies` tool)

**Returns:**

* `int`: The number of movies matching the criteria. Returns `0` if an error occurs.

### `get_average_rating`

Calculates the average rating for movies matching the criteria, for a specific rating type.

```python
def get_average_rating(
rating_field_key: str,
genres: Optional[Union[List[str], str]] = None,
actors: Optional[Union[List[str], str]] = None,
directors: Optional[Union[List[str], str]] = None,
writers: Optional[Union[List[str], str]] = None,
year: Optional[int] = None,
start_year: Optional[int] = None,
end_year: Optional[int] = None
) -> Optional[Dict[str, Any]]:
```

**Args:**

* `rating_field_key` (str): The key for the rating source (e.g., "imdb", "metacritic", "tomatoes_viewer", "tomatoes_critic").
* (Other filtering arguments are similar to those in `find_movies`/`count_movies`, excluding `title`, `min_ratings`, and `rated_mpaa` as they are less common for broad average calculations).

**Returns:**

* `Optional[Dict[str, Any]]`: A dictionary containing `'average_rating'` (float, rounded to 2 decimal places) and `'movie_count'` (int). Returns `None` if the `rating_field_key` is invalid, or a dict with `None` average_rating and `0` count if no movies match or an error occurs.

## Contributing

Contributions are welcome! If you have suggestions for improvements, new features, or bug fixes, please open an issue or submit a pull request.

## License

This project is open-sourced under the MIT License. See the `LICENSE` file for more details.