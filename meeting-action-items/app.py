"""
app.py
-------
Flask web server for the Meeting-to-Action-Items pipeline.

Routes:
    GET  /                -> serves the UI
    POST /api/extract     -> takes transcript text, returns structured
                              action items as JSON

Runs fully offline with the rule-based extractor by default - no API
keys, no external calls, no internet required.
"""

from flask import Flask, render_template, request, jsonify

from extractor import extract_action_items

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(force=True)
    transcript = data.get("transcript", "").strip()
    meeting_date = data.get("meeting_date") or None

    if not transcript:
        return jsonify({"error": "Transcript text is empty."}), 400

    try:
        items = extract_action_items(transcript, meeting_date=meeting_date)
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500

    return jsonify({
        "count": len(items),
        "items": items,
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
