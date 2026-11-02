# app/ai — everything that talks to an AI model lives in this package.
#
#   service.py  AIService: render a prompt, call the provider, validate the JSON, retry
#   gemini.py   the Google Gemini provider (the only file that imports the Gemini SDK)
#   prompts.py  loads prompts/*.md
#   schemas.py  the JSON shape each prompt must answer with
#   errors.py   friendly errors shown to the user
#
# Switching to another provider (Claude, OpenAI...) means writing one class with the
# same generate_json() method as GeminiProvider and choosing it in service.get_ai().
