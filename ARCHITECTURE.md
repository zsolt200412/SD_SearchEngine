# Local Search Engine Architecture

This document describes the architecture of the Local Search Engine using the C4 model.

# 1. System Context

The Local Search Engine allows users to search files stored on their local device, including documents, media, and other files. The system indexes file names, content, and metadata to provide fast search results.

## Actors
- User – performs searches for local files
- Administrator – configures indexing settings (e.g., root directories, ignore rules)

## External Systems
- Local File System – source of files to be indexed

## Context Diagram

User -> Local Search Engine -> Indexed Files Database  
Administrator -> Local Search Engine  
Local Search Engine -> Local File System


# 2. Containers

The system is composed of several containers.

## User Interface
Technology: HTML / JavaScript / React (or a desktop UI framework)

Responsibilities:
- Accept search queries from the user
- Display search results
- Show file previews and metadata

## Search API
Technology: Python / Java / Node.js

Responsibilities:
- Receive search queries
- Process and interpret queries
- Communicate with the index database
- Return ranked results

## Indexing Service

Responsibilities:
- Traverse the local filesystem
- Extract file content and metadata
- Update the searchable index
- Detect modified files for incremental indexing

## Database / Index Store
Technology: PostgreSQL / SQLite / ElasticSearch

Responsibilities:
- Store indexed file information
- Store metadata (file path, extension, timestamps)
- Provide fast lookup for search queries


# Container Diagram

User  
  |  
  v  
User Interface  
  |  
  v  
Search API  
  |  
  +-----> Index Database  
  |  
  +-----> Indexing Service  
             |  
             v  
        Local File System


# 3. Components

Inside the **Search API** container.

## Query Controller
Handles incoming search requests from the user interface.

## Query Processor
Tokenizes and processes search queries.

## Ranking Engine
Ranks matching files based on relevance.

## Result Formatter
Formats search results and file previews for the frontend.


# Component Diagram

Search API  
 ├── Query Controller  
 ├── Query Processor  
 ├── Ranking Engine  
 └── Result Formatter  


# 4. Code (Classes)

Example classes inside the Ranking Engine.

class QueryParser  
class IndexSearcher  
class RankCalculator  
class ResultFormatter  


## Responsibilities

### QueryParser
- parseQuery() – parses and tokenizes user queries.

### IndexSearcher
- searchIndex() – queries the indexed database for matching files.

### RankCalculator
- computeScore() – calculates relevance scores for search results.

### ResultFormatter
- formatResults() – formats results and prepares file previews for display.