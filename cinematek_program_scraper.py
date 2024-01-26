import requests
import datetime
from bs4 import BeautifulSoup, NavigableString
import imdb # pip install IMDbPY
import os
import webbrowser
import urllib.parse
from threading import Thread

# Le cache pour rediff pourrait inclure toutes les données du film, pas que le nom

# Le programme de Flagey est sur https://www.flagey.be/en/program/2-cinema

def main(pgm_days_number, min_note):
    output = "cinematek_program.html" # init
    
    # getting cinematek's program
    pgm_url = "https://cinematek.be/fr/programme/calendrier"
    pgm_html = requests.get(pgm_url).content # view-source is different than the soup
    
    # extracting movies
    soup = BeautifulSoup(pgm_html, "html.parser")
    
    imdb_ia = imdb.IMDb() # int (ia = imdb instance)
    init(output) # init
    
    with open(output, "a") as file:
        file.write(f"<h3> Programme avec note IMDb &ge; {min_note}</h3>")
        file.write(f"<h3><a href=\"https://cinematek.be/fr/programme/calendrier\" target=\"_blank\">Programme Cinematek</a></h3>")
        # file.write("<br>")
        file.write("<table>\n")
        films_long_titles = set() # init
        for i in range(pgm_days_number):
            get_program(i, soup, imdb_ia, file, films_long_titles)
        file.write("</table>\n")
        finalize(file)
    
    print(f"Output file: {os.getcwd()}\\{output}")
    webbrowser.open(f"{os.getcwd()}\\{output}")

def get_program(day, soup, imdb_ia, file, films_long_titles):
    date = datetime.date.today() + datetime.timedelta(days=day)
    week_day = get_week_day(date)
    year, month, day = date.strftime("%Y"), date.strftime("%m"), date.strftime("%d")
    print(f"[INFO] Checking program for {day}/{month}/{year}...")
    file.write("<tr>\n")
    file.write(f"<td bgcolor=\"lightgreen\"><b>{week_day} {day}/{month}/{year}</b></td>\n")
    file.write("</tr>\n")
    
    films = soup.findAll("a", {"data-date": f"{year}{month}{day}"})
    
    threads = []
    res = []  # [{"film_time": "18:00", "film_title": "Titanic", "film_rating": 7.6, "url": "https://www.imdb.com/title/tt0120338}, ...]
    for film in films:
        threads.append(Thread(target=parse, args=(film, films_long_titles, imdb_ia, min_note, res)))
    for thread in threads:
        thread.daemon = True # exit thread when main process exits
        thread.start()
    for thread in threads:
        thread.join() # join stops main process to wait for the threads to finish
    
    # sorting results by projection time
    def get_time(elem):
        return elem["time"]
    res.sort(key=get_time)

    if len(res) > 0:
        # table_headers(file)
        for film_data in res:
            write_table_row(file, film_data)

def write_table_row(file, film_data):
    if film_data["title"].startswith("[REDIFF]"):
        file.write("<tr style=\"color:grey\">\n")
    else:
        file.write("<tr bgcolor=\"#eee\">\n")
        
    file.write(f"<td><b>{film_data['time']}</b></td>\n")
    
    if film_data["title"].startswith("[REDIFF]"):
        file.write(f"<td>[REDIFF]</td>\n") # No image
        file.write(f"<td>{film_data['title']}</td>\n")
    else:
        file.write(f"<td><a href=\"{film_data['url'].replace(' ', ' ')}\" target=\"_blank\"><img src=\"{film_data['image']}\"></a></td>\n")
        # encoding problem with unicode char \u2009 => replace with normal space
        file.write(f"<td><a href=\"{film_data['url'].replace(' ', ' ')}\" target=\"_blank\">{film_data['title'].replace(' ', ' ')}</a></td>\n")
        
    file.write(f"<td>{film_data['director']}</td>\n")
    file.write(f"<td>{film_data['plot']}</td>\n")
    file.write(f"<td><b>{film_data['year']}</b></td>\n")
    file.write(f"<td>{film_data['countries']}</td>\n")
    file.write("</tr>\n")

def parse(film, films_long_titles, imdb_ia, min_note, res, film_time=None):
    # getting film title from html
    film = BeautifulSoup(str(film), "html.parser") # somehow was mandatory
    # try:
    temp = film.find_all("span", {"class": "lead text-color film__title film__titles"})
    if temp == []:
        temp = film.find_all("span", {"class": "text-color film__title film__titles"})
    if len(temp) > 1:
        # If two results it means it's at the same time and it's specified only once in the html
        film_time = film.find("h4", {"class": "text-black case screening__time"}).contents # ['18', <span>:</span>, '00']
        film_time = f"{film_time[0]}:{film_time[2]}"
        print(f"[DEBUG] More than one movie at {film_time}:")
        print(temp) # 18:00
        print("=> calling parse on all results")
        for result in temp:
            parse(BeautifulSoup(str(result), "html.parser"), films_long_titles, imdb_ia, min_note, res, film_time)
        return
    film_title_elems = temp[0].contents
    if not isinstance(film_title_elems, list): # for example film_title_elems = <strong>Dialogue d’ombres</strong>
        film_title_elems = [str(film_title_elems)]

    for i in range(len(film_title_elems)):
        if not isinstance(film_title_elems[i], str):
            temp = str(film_title_elems[i])
            if "<strong>" in temp and "</strong>" in temp:
                film_title = temp[temp.find("<strong>")+len("<strong>"):temp.find("</strong>")]
                film_title_elems[i] = f"<b>{film_title}</b>"
            else:
                film_title_elems[i] = temp
                
    film_long_title = ''.join(film_title_elems) # ['Elisso ⁄ ', '<b>Eliso</b>'] -> 'Elisso ⁄ <b>Eliso</b>'
    film_long_title = film_long_title.replace("⁄", "/")             # 'Elisso ⁄ <b>Eliso</b>' -> 'Elisso / <b>Eliso</b>'
    
    if film_long_title not in films_long_titles:
        films_long_titles.add(film_long_title)
    else:
        film_long_title = f"[REDIFF] {film_long_title}"
    
    print(f"[INFO]     Searching {film_title} on IMDb...")
    
    imdb_connection_fail = True # init to True to enter the loop
    while imdb_connection_fail:
        try:
            imdb_res = imdb_ia.search_movie(film_title)
            imdb_connection_fail = False
        except:
            print("[DEBUG] Could not reach IMDB, retrying...")
        if not imdb_connection_fail:
            try:
                imdb_first_res = imdb_res[0] # taking first result
                imdb_connection_fail = False
            except:
                print(f"[WARNING] \"{film_title}\" not found on IMDb! Passing.")
                return
            film_code = imdb_first_res.movieID
            try:
                film_object = imdb_ia.get_movie(film_code)
            except:
                print("[DEBUG] Could not reach IMDB, retrying...")
                imdb_connection_fail = True
            if not imdb_connection_fail:
                try:
                    film_url = imdb_ia.get_imdbURL(film_object)
                except:
                    print("[DEBUG] Could not reach IMDB, retrying...")
                    imdb_connection_fail = True

    film_data = film_object.data
    
    if "rating" in film_data: # sometimes there is no rating on IMDb
        film_rating = film_data["rating"]
    else:
        film_rating = 0
    
    if "year" in film_data:
        film_year = film_data["year"]
    else:
        film_year = "?"
    
    if "director" in film_data:  # sometimes there is no director on IMDb
        film_director = film_data["director"][0].data["name"]
    else:
        film_director = "?"

    if "plot" in film_data:
        film_plot = film_data["plot"][0]
    else:
        film_plot = "?"

    if "countries" in film_data:
        film_countries = ", ".join(film_data["countries"])
    else:
        film_countries = "?"
    
    if "cover url" in film_data:
        film_image = film_data["cover url"]
    else:
        film_image = "https://images.emojiterra.com/google/android-marshmallow/128px/1f39e.png"
    
    # considering movie only if note is good enough
    if film_rating >= min_note:
        # getting film projection time from html
        if not film_time:
            film_time = film.find("h4", {"class": "text-black case screening__time"}).contents # ['18', <span>:</span>, '00']
            film_time = f"{film_time[0]}:{film_time[2]}" # 18:00
        # getting film trailer
        # film_trailer = f"https://www.youtube.com/results?search_query={urllib.parse.quote(film_title).replace('%20', '+')}+{urllib.parse.quote(film_director).replace('%20', '+')}+{film_year}+trailer"
        res.append({"time": film_time, "title": film_long_title, "rating": film_rating, "year": film_year, "director": film_director, "plot": film_plot, "image": film_image, "countries": film_countries, "url": film_url})

def table_headers(file):
    file.write("<tr>\n")
    file.write("<th>Heure</th>\n")
    file.write("<th>Image</th>\n")
    file.write("<th>Réalisateur</th>\n")
    file.write("<th>Titre</th>\n")
    file.write("<th>Synopsis</th>\n")
    file.write("<th>Année</th>\n")
    file.write("<th>Pays</th>\n")
    file.write("</tr>\n")

def get_week_day(date):
    week_day = date.weekday() # 0-6
    options = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"}
    return options[week_day]

def init(output):
    with open(output, "w") as file:
        # beginning output
        file.write("<!DOCTYPE html>\n")
        file.write("<html>\n")
        file.write("<head>\n")
        
        # CSS for table
        file.write("<style>\n")
        file.write("table {\n")
        file.write("  font-family: arial, sans-serif;\n")
        file.write("  border-collapse: collapse;\n")
        file.write("  width: 100%;\n")
        file.write("  border-left: none;n")
        file.write("  border-right: none;n")
        file.write("}\n")
        file.write("td, th {\n")
        file.write("  border: 2.5px solid #dddddd;\n")
        file.write("  text-align: left;\n")
        file.write("  padding: 8px;\n")
        file.write("  border-left: none;n")
        file.write("  border-right: none;n")
        file.write("}\n")
        file.write("</style>\n")
            
        file.write("</head>\n")
        file.write("<body>\n")

def finalize(file):
    file.write("</body>\n")
    file.write("</html>")

if __name__ == '__main__':
    # clearing terminal
    os.system('cls' if os.name == 'nt' else 'clear')

    # inputs
    pgm_days_number = int(input("Regarder combien de jours dans le futur? (1-60): ")) # number of days of the program we want to look into (>= 1)
    min_note = input("Note IMDb minimale? (0-10): ") # minimum note we consider
    if "," in min_note:
        min_note = min_note.replace(",", ".")
    min_note = float(min_note)
    
    # main
    main(pgm_days_number, min_note)