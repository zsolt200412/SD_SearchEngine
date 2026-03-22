# Search Engine Architecture

This document describes the architecture of the Search Engine using the C4 model.

# 1. System Context

The Search Engine allows users to search documents indexed from the web.

## Actors
- User – performs searches
- Administrator – manages indexing and system configuration

## External Systems
- Internet websites (source of documents)

## Context Diagram

User -> Search Engine -> Indexed Documents Database
Administrator -> Search Engine
Search Engine -> Internet Websites

# 2. Containers

The system is composed of several containers.

## Web Interface
Technology: HTML / JavaScript / React

Responsibilities:
- Accept search queries
- Display results to users

## Search API
Technology: Python / Java / Node.js

Responsibilities:
- Receive queries
- Process search requests
- Communicate with the index

## Indexing Service
Responsibilities:
- Crawl websites
- Extract text
- Build searchable index

## Database / Index Store
Technology: PostgreSQL / ElasticSearch / custom index

Responsibilities:
- Store indexed documents
- Provide fast lookup for queries

# Container Diagram

User
  |
  v
Web Interface
  |
  v
Search API
  |
  +-----> Index Database
  |
  +-----> Indexing Service
             |
             v
        Internet Websites

# 3. Components

Inside the Search API container.

## Query Controller
Handles incoming search requests.

## Query Processor
Tokenizes and processes queries.

## Ranking Engine
Ranks documents based on relevance.

## Result Formatter
Formats results for the frontend.

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

Responsibilities:

QueryParser
- parseQuery()

IndexSearcher
- searchIndex()

RankCalculator
- computeScore()

ResultFormatter
- formatResults()