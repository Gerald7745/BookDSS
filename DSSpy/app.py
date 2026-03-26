from email.policy import default

import pandas as pd
import os
from flask import Flask, render_template, request

app = Flask(__name__)

# Load dataset
df = pd.read_csv('books.csv')
# Preprocess: split formats into list for easier checking
df['formats_list'] = df['formats'].apply(lambda x: x.split(',') if pd.notna(x) else [])

def recommend(prefs, weights):
    """
    prefs: dict with keys: genres (list), author (str), year_min, year_max,
           rating_min, price_max, age_rating (str), completion (str),
           formats (list), region (str)
    weights: dict with keys: genre, author, rating, price, age, completion, format
    returns: DataFrame with scores sorted descending
    """
    
    books = df.copy()
    
    
    if prefs.get('author'):
        books = books[books['author'].str.contains(prefs['author'], case=False, na=False)]
    if prefs.get('year_min'):
        books = books[books['year'] >= int(prefs['year_min'])]
    if prefs.get('year_max'):
        books = books[books['year'] <= int(prefs['year_max'])]
    if prefs.get('rating_min'):
        books = books[books['rating'] >= float(prefs['rating_min'])]
    if prefs.get('price_max'):
        books = books[books['price'] <= float(prefs['price_max'])]
    if prefs.get('age_rating'):
        books = books[books['age_rating'] == prefs['age_rating']]
    if prefs.get('completion'):
        books = books[books['completion'] == prefs['completion']]
    if prefs.get('region'):
        books = books[books['region'] == prefs['region']]
    
    if books.empty:
        return books  # empty
    
    # --- Normalize numeric columns for scoring ---
    # Rating: /5
    books['score_rating'] = books['rating'] / 5.0
    
    # Price: lower is better; normalize between 0 and 1 using min-max of filtered set
    min_price = books['price'].min()
    max_price = books['price'].max()
    if max_price > min_price:
        books['score_price'] = 1 - (books['price'] - min_price) / (max_price - min_price)
    else:
        books['score_price'] = 1.0  # all same price
    
    # Genre match: binary (1 if book's genre in user selected genres)
    if prefs.get('genres'):
        books['score_genre'] = books['genre'].apply(lambda g: 1 if g in prefs['genres'] else 0)
    else:
        books['score_genre'] = 0  # no preference
    

    if prefs.get('author'):
        books['score_author'] = 1
    else:
        books['score_author'] = 0
    
    # Age rating match: after filter, all match -> score = 1 if preference given else 0
    if prefs.get('age_rating'):
        books['score_age'] = 1
    else:
        books['score_age'] = 0
    
    # Completion match: same logic
    if prefs.get('completion'):
        books['score_completion'] = 1
    else:
        books['score_completion'] = 0
    
    # Format match: binary if any selected format is in book's formats
    if prefs.get('formats'):
        books['score_format'] = books['formats_list'].apply(
            lambda fmts: 1 if any(f in fmts for f in prefs['formats']) else 0
        )
    else:
        books['score_format'] = 0
    
    # --- Calculate total weighted score ---
    total_weight = sum(weights.values())
    if total_weight == 0:
        total_weight = 1  # avoid division by zero
    
    books['total_score'] = (
        weights.get('genre', 0) * books['score_genre'] +
        weights.get('author', 0) * books['score_author'] +
        weights.get('rating', 0) * books['score_rating'] +
        weights.get('price', 0) * books['score_price'] +
        weights.get('age', 0) * books['score_age'] +
        weights.get('completion', 0) * books['score_completion'] +
        weights.get('format', 0) * books['score_format']
    ) / total_weight  # normalize to 0-1 range
    
    # Sort descending
    result = books.sort_values('total_score', ascending=False)
    return result[['title', 'author', 'genre', 'year', 'rating', 'price', 'age_rating', 'completion', 'formats', 'total_score']]

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        prefs = {
            'genres': request.form.getlist('genres'),
            'author': request.form.get('author', ''),
            'year_min': request.form.get('year_min', ''),
            'year_max': request.form.get('year_max', ''),
            'rating_min': request.form.get('rating_min', ''),
            'price_max': request.form.get('price_max', ''),
            'age_rating': request.form.get('age_rating', ''),
            'completion': request.form.get('completion', ''),
            'formats': request.form.getlist('formats'),
            'region': request.form.get('region', '')
        }
        
        
       
        def safe_float(value, default=1.0):
            try:
                return float(value) if value and value.strip() else default
            except ValueError:
                return default

        weights = {
            'genre': safe_float(request.form.get('weight_genre')),
            'author': safe_float(request.form.get('weight_author')),
            'rating': safe_float(request.form.get('weight_rating')),
            'price': safe_float(request.form.get('weight_price')),
            'age': safe_float(request.form.get('weight_age')),
            'completion': safe_float(request.form.get('weight_completion')),
            'format': safe_float(request.form.get('weight_format'))
            }
        # Call recommendation engine
        results = recommend(prefs, weights)
        return render_template('results.html', tables=[results.to_html(classes='data', index=False)], titles=results.columns.values)
        
    # GET: show form
    # Get unique values for dropdowns
    unique_authors = sorted(df['author'].unique())
    unique_genres = sorted(df['genre'].unique())
    unique_age = df['age_rating'].unique()
    unique_completion = df['completion'].unique()
    unique_formats = set()
    for fmts in df['formats_list']:
        unique_formats.update(fmts)
    unique_formats = sorted(unique_formats)
    unique_regions = df['region'].unique()
    
    featured_books = df.nlargest(6, 'rating')[['title', 'author', 'year', 'rating']].to_dict('records')
    
    # Convert the entire DataFrame to a list of dictionaries for client-side filtering
    books_data = df.to_dict(orient='records')
     
    return render_template('index.html',
                           authors=unique_authors,
                           genres=unique_genres,
                           age_ratings=unique_age,
                           completions=unique_completion,
                           formats=unique_formats,
                           regions=unique_regions,
                           featured=featured_books,
                           books_data=books_data)   
                            
if __name__ == '__main__':
    app.run(debug=True)