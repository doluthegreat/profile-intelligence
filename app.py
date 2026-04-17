import os
import asyncio
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
from uuid6 import uuid7

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def get_age_group(age):
    if age <= 12: return 'child'
    if age <= 19: return 'teenager'
    if age <= 59: return 'adult'
    return 'senior'

def format_timestamp(dt):
    return dt.isoformat().replace('+00:00', 'Z')

async def fetch_upstream_data(name):
    async with httpx.AsyncClient() as client:
        # Concurrent calls
        tasks = [
            client.get(f"https://api.genderize.io?name={name}"),
            client.get(f"https://api.agify.io?name={name}"),
            client.get(f"https://api.nationalize.io?name={name}")
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        try:
            g_data = responses[0].json()
            a_data = responses[1].json()
            n_data = responses[2].json()
        except:
            raise ValueError("Upstream")

    if not g_data.get('gender') or g_data.get('count') == 0: raise ValueError("Genderize")
    if a_data.get('age') is None: raise ValueError("Agify")
    if not n_data.get('country'): raise ValueError("Nationalize")

    top_country = sorted(n_data['country'], key=lambda x: x['probability'], reverse=True)[0]

    return {
        "gender": g_data['gender'],
        "gender_probability": g_data['probability'],
        "sample_size": g_data['count'],
        "age": a_data['age'],
        "age_group": get_age_group(a_data['age']),
        "country_id": top_country['country_id'],
        "country_probability": top_country['probability']
    }

@app.route('/api/profiles', methods=['POST'])
async def create_profile():
    try:
        data = request.get_json()
        name = data.get('name', '').strip().lower()
    except:
        return jsonify({"status": "error", "message": "Invalid type"}), 422

    if not name:
        return jsonify({"status": "error", "message": "Missing or empty name"}), 400

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE name = %s", (name,))
            existing = cur.fetchone()
            if existing:
                existing['id'] = str(existing['id'])
                existing['created_at'] = format_timestamp(existing['created_at'])
                return jsonify({"status": "success", "message": "Profile already exists", "data": existing}), 200

            try:
                enriched = await fetch_upstream_data(name)
            except ValueError as e:
                return jsonify({"status": "502", "message": f"{str(e)} returned an invalid response"}), 502

            profile_id = str(uuid7())
            created_at = datetime.now(timezone.utc)
            record = {"id": profile_id, "name": name, **enriched, "created_at": created_at}
            
            query = """INSERT INTO profiles (id, name, gender, gender_probability, sample_size, age, age_group, country_id, country_probability, created_at)
                       VALUES (%(id)s, %(name)s, %(gender)s, %(gender_probability)s, %(sample_size)s, %(age)s, %(age_group)s, %(country_id)s, %(country_probability)s, %(created_at)s)"""
            cur.execute(query, record)
            conn.commit()
            
            record['created_at'] = format_timestamp(created_at)
            return jsonify({"status": "success", "data": record}), 201

@app.route('/api/profiles/<id>', methods=['GET'])
def get_one(id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE id = %s", (id,))
            p = cur.fetchone()
            if not p: return jsonify({"status": "error", "message": "Profile not found"}), 404
            p['id'], p['created_at'] = str(p['id']), format_timestamp(p['created_at'])
            return jsonify({"status": "success", "data": p})

@app.route('/api/profiles', methods=['GET'])
def get_all():
    g, c, a = request.args.get('gender'), request.args.get('country_id'), request.args.get('age_group')
    sql = "SELECT id, name, gender, age, age_group, country_id FROM profiles WHERE 1=1"
    params = []
    if g: sql += " AND gender = %s"; params.append(g.lower())
    if c: sql += " AND country_id = %s"; params.append(c.upper())
    if a: sql += " AND age_group = %s"; params.append(a.lower())
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            for r in rows: r['id'] = str(r['id'])
            return jsonify({"status": "success", "count": len(rows), "data": rows})

@app.route('/api/profiles/<id>', methods=['DELETE'])
def delete_one(id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM profiles WHERE id = %s", (id,))
            if cur.rowcount == 0: return jsonify({"status": "error", "message": "Profile not found"}), 404
            conn.commit()
    return '', 204