# Implementation Decisions

## 1. Application Structure

All application endpoints, validation logic, business rules, and database operations are implemented in `app/main.py`, as required by the assignment.

## 2. Framework and Validation

FastAPI provides the REST API and Swagger documentation. Pydantic models validate incoming request data and reject invalid inputs.

## 3. Database Design

MongoDB stores employee information and attendance records in separate collections, following the supplied data model. PyMongo is used for database operations.

## 4. Date and Time Handling

The implementation follows the API contract for epoch-millisecond timestamps, UTC storage of instants, IST attendance dates, and overnight shifts.

## 5. Indexing

MongoDB indexes are created during application startup to support the required query patterns, sorting, and uniqueness constraints.

## 6. Attendance Business Rules

Attendance calculations follow the supplied business rules for punch-in, punch-out, late arrival, overtime, work hours, half-days, and rounding.

## 7. Regularization and Audit History

Attendance regularization validates permitted changes and records the reason, regularizing user, and actual changes in the record's audit history.

## 8. Analytics

Analytics endpoints calculate employee attendance statistics, department summaries, late-arrival rankings, and department attendance trends according to the API contract.

## 9. Error Handling

The API returns appropriate HTTP status codes for successful operations, validation errors, missing resources, conflicting operations, and database connectivity failures.