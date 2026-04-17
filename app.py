import os
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
from uuid6 import uuid7

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not set")


# ---------------- DB ----------------
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ---------------- Utils ----------------
def format_timestamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def get_age_group(age):
    if age <= 12:
        return "child"
    if age <= 19:
        return "teenager"
    if age <= 59:
        return "adult"
    return "senior"


# ---------------- External APIs ----------------
def fetch_upstream_data(name):
    with httpx.Client(timeout=10) as client:
        gender = client.get(f"https://api.genderize.io?name={name}").json()
        age = client.get(f"https://api.agify.io?name={name}").json()
        country = client.get(f"https://api.nationalize.io?name={name}").json()

    if not gender.get("gender") or gender.get("count", 0) == 0:
        raise ValueError("Genderize failed")

    if age.get("age") is None:
        raise ValueError("Agify failed")

    if not country.get("country"):
        raise ValueError("Nationalize failed")

    top_country = max(country["country"], key=lambda x: x["probability"])

    return {
        "gender": gender["gender"],
        "gender_probability": gender["probability"],
        "sample_size": gender["count"],
        "age": age["age"],
        "age_group": get_age_group(age["age"]),
        "country_id": top_country["country_id"],
        "country_probability": top_country["probability"]
    }


# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return {"status": "ok", "message": "API running"}


@app.route("/api/profiles", methods=["POST"])
def create_profile():
    data = request.get_json()
    name = data.get("name", "").strip().lower()

    if not name:
        return jsonify({"error": "Missing name"}), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT * FROM profiles WHERE name = %s", (name,))
            existing = cur.fetchone()

            if existing:
                existing["id"] = str(existing["id"])
                existing["created_at"] = format_timestamp(existing["created_at"])
                return jsonify(existing), 200

            try:
                enriched = fetch_upstream_data(name)
            except Exception as e:
                return jsonify({"error": str(e)}), 502

            profile_id = str(uuid7())
            created_at = datetime.now(timezone.utc)

            record = {
                "id": profile_id,
                "name": name,
                **enriched,
                "created_at": created_at
            }

            cur.execute("""
                INSERT INTO profiles (
                    id, name, gender, gender_probability,
                    sample_size, age, age_group,
                    country_id, country_probability, created_at
                )
                VALUES (
                    %(id)s, %(name)s, %(gender)s, %(gender_probability)s,
                    %(sample_size)s, %(age)s, %(age_group)s,
                    %(country_id)s, %(country_probability)s, %(created_at)s
                )
            """, record)

            conn.commit()

            record["created_at"] = format_timestamp(created_at)
            return jsonify(record), 201


@app.route("/api/profiles/<id>", methods=["GET"])
def get_profile(id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE id = %s", (id,))
            row = cur.fetchone()

            if not row:
                return jsonify({"error": "Not found"}), 404

            row["id"] = str(row["id"])
            row["created_at"] = format_timestamp(row["created_at"])
            return jsonify(row)


@app.route("/api/profiles", methods=["GET"])
def get_all():
    gender = request.args.get("gender")
    country = request.args.get("country_id")
    age_group = request.args.get("age_group")

    sql = "SELECT id, name, gender, age, age_group, country_id FROM profiles WHERE 1=1"
    params = []

    if gender:
        sql += " AND gender = %s"
        params.append(gender.lower())

    if country:
        sql += " AND country_id = %s"
        params.append(country.upper())

    if age_group:
        sql += " AND age_group = %s"
        params.append(age_group.lower())

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

            for r in rows:
                r["id"] = str(r["id"])

            return jsonify({
                "count": len(rows),
                "data": rows
            })


@app.route("/api/profiles/<id>", methods=["DELETE"])
def delete_profile(id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM profiles WHERE id = %s", (id,))

            if cur.rowcount == 0:
                return jsonify({"error": "Not found"}), 404

            conn.commit()

    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)