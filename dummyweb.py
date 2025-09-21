from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "I'm alive and running on Render!"

if __name__ == "__main__":
    # Use Render's port if available, otherwise default to 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
