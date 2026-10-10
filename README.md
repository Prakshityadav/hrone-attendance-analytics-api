# Employee Attendance & Analytics API

## Overview

A REST API built with Python, FastAPI, and MongoDB for employee management, attendance tracking, attendance regularization, and attendance analytics.

## Tech Stack

* Python
* FastAPI
* MongoDB 6.0+
* PyMongo
* Pydantic

## Prerequisites

* Python installed
* MongoDB 6.0 or newer running locally or accessible through MongoDB Atlas
* Dependencies listed in `requirements.txt`

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure `MONGO_URI` and `MONGO_DB` as environment variables using your local environment configuration. Do not commit your `.env` file or credentials.

If using the supplied sample data, run:

```bash
python sample_seed.py
```

## Run the API

From the project root, run:

```bash
uvicorn app.main:app --port 8000
```

Open Swagger UI at:

http://127.0.0.1:8000/docs

## Features

* Employee creation and listing
* Attendance punch-in and punch-out
* Attendance filtering and pagination
* Attendance regularization with audit history
* Monthly employee analytics
* Department summaries
* Late-arrival leaderboard
* Department attendance trends
* Query execution-plan inspection

## Project Structure

```text
app/
└── main.py
requirements.txt
README.md
REVIEW.md
DECISIONS.md
```