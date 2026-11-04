from flask import Flask
from datetime import datetime

app = Flask(__name__)
LOG_FILE = "/data/app.log"

@app.route("/")
def index():
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - visit\n")
    return "Visit logged!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
