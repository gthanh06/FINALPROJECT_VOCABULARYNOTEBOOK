# app — Vocabulary Notebook backend.
#
# Running locally without Docker, settings come from a .env file next to the code
# (see .env.example). Variables already set in the environment win, so Docker,
# Render and the tests are not affected. .env is never committed.
from dotenv import load_dotenv

load_dotenv()
