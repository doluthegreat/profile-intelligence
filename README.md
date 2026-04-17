# PROFILE-INTELLIGENCE-API

A REST API that accepts a name, enriches it using three external APIs (Genderize, Agify, Nationalize), stores the result, and allows retrieval and management of stored profiles. Deployed to AWS EC2 @ **Profile Intelligence Service 🧠 🌍 👤**

---

## SUMMARY

This service exposes four RESTful endpoints to create, retrieve, list, and delete name-based profiles. When a name is submitted, the API simultaneously queries Genderize (for gender prediction), Agify (for age prediction), and Nationalize (for country of origin prediction). The results are aggregated, processed, and stored in a PostgreSQL database. Each profile is assigned a UUID v7 ID and a UTC timestamp on creation. Idempotency is enforced — submitting the same name twice does not create a duplicate record; the existing profile is returned instead. All responses follow a consistent JSON structure. The entire application is containerized using Docker and runs on an AWS EC2 instance.

---

## TECHNOLOGY USED

* **Python**
* **Flask**
* **PostgreSQL**
* **Docker & Docker Compose**
* **AWS EC2**
* **Genderize API** — https://api.genderize.io
* **Agify API** — https://api.agify.io
* **Nationalize API** — https://api.nationalize.io

---

## SETTING UP LOCALLY

To set up locally, follow the steps below:

* Clone the repository
```bash
git clone https://github.com/doluthegreat/profile-intelligence
```

* Navigate into the project directory
```bash
cd profile-intelligence
```

* Install dependencies (use a virtual environment)
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

* Create and set up the database
```bash
createdb profile_intelligence
psql -d profile_intelligence -f schema.sql
```

* Set your database URL as an environment variable (optional — defaults to the value below)
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/profile_intelligence"
```

* Start the server
```bash
python app.py
```

If all of the above was done correctly, the server should start on `http://localhost:5000`.

---

## SETTING UP WITH DOCKER 

* Make sure Docker and Docker Compose are installed

* Build and start both the app and database containers
```bash
docker compose up --build -d
```

* Run the schema to create the database table (first time only)
```bash
docker exec -i profile-intelligence-db-1 psql -U user -d profiles_db < schema.sql
```

* Confirm both containers are running
```bash
docker ps
```

The API will be available at `http://localhost:5000`.

---

## MAKING REQUESTS

### POST /api/profiles
Creates a new profile for a given name. If the name already exists, returns the existing profile.

**Request**
```bash
curl -X POST http://localhost:5000/api/profiles \
  -H "Content-Type: application/json" \
  -d '{"name": "ella"}'
```

**Response (201 — created)**
```json
{
  "status": "success",
  "data": {
    "id": "019d9d5a-324e-7de8-b13e-1ee1cffaafb0",
    "name": "ella",
    "gender": "female",
    "gender_probability": 0.99,
    "sample_size": 97517,
    "age": 53,
    "age_group": "adult",
    "country_id": "CM",
    "country_probability": 0.097,
    "created_at": "2026-04-17T21:30:27Z"
  }
}
```

**Response (200 — already exists)**
```json
{
  "status": "success",
  "message": "Profile already exists",
  "data": { "...existing profile..." }
}
```

---

### GET /api/profiles
Returns all stored profiles. Supports optional case-insensitive query filters.

**Request**
```bash
curl http://localhost:5000/api/profiles
```

