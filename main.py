from flask import Flask, render_template, request, abort
from urllib.parse import urlparse

from DreamEngine import *

app = Flask(__name__)
app.secret_key = "example"
engine = DreamEngine()

@app.route('/favicon.ico')
def favicon():
    # Return 404 for favicon requests to prevent page generation
    abort(404)

@app.route("/", defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    # Ignore common browser requests for static files
    if path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
        abort(404)
    
    # Handle search and no search
    query = request.args.get("query")
    if not query and not path:
        return get_index()
    if query and not path:
        return engine.get_search(query)
    
    # Generate the page
    parsed_path = urlparse("http://" + path)
    generated_page = engine.get_page(parsed_path.netloc, path=parsed_path.path)
    return generated_page

def get_index():
    # Render the Flask template home.html
    return render_template('index.htm')

if __name__ == "__main__":
    app.run()
