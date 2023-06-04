from flask import Flask, render_template, flash
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import requests
from datetime import datetime, timezone
from geopy.geocoders import Nominatim
import arrow
import pandas as pd
import plotly.graph_objects as go
from tabulate import tabulate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'SECRET_KEY'
Bootstrap(app)


# ask user for the location with a simple Flask Form

class FCForm(FlaskForm):
    name = StringField("Name of the beach or city", validators=[DataRequired()])
    submit = SubmitField("Search forecast")


@app.route('/', methods=['GET', 'POST'])
def home():
    form = FCForm()
    if form.validate_on_submit():
        geolocator = Nominatim(user_agent="MyApp")
        API_KEY_RL = "SECRET_KEY"

# turn input location into lat and long values to be accepted from the stormglass API
        location = geolocator.geocode(form.name.data)

        lat = location.latitude
        lon = location.longitude
        start = arrow.now().floor('day')
        end = arrow.now().ceil('day')
        try:
            response = requests.get('https://api.stormglass.io/v2/weather/point',
                                    params={
                                        'lat': lat,
                                        'lng': lon,
                                        'params': ','.join(
                                            ['windSpeed', 'windDirection', 'airTemperature',
                                             'waterTemperature', 'seaLevel', 'swellHeight',
                                             'waveDirection', 'waveHeight', 'wavePeriod',
                                             'currentDirection', 'currentSpeed']),
                                        'start': start.to('UTC').timestamp(),
                                        'end': end.to('UTC').timestamp()

                                    },
                                    headers={'Authorization': API_KEY_RL}
                                    )

            data = response.json()
            hourly_data = data['hours']

# save the required data requested from the  API as .csv file

            data_output = []
            for hour in hourly_data:
                data_output.append({'time': hour['time'],
                                    'air_temp': hour['airTemperature']['noaa'],
                                    'water_temp': hour['waterTemperature']['noaa'],
                                    'current_dir': hour['currentDirection']['meto'],
                                    'current_speed': hour['currentSpeed']['meto'],
                                    'sea_lvl': hour['seaLevel']['meto'],
                                    'swell_height': hour['swellHeight']['meteo'],
                                    'wave_dir': hour['waveDirection']['meteo'],
                                    'wave_hei': hour['waveHeight']['meteo'],
                                    'wave_per': hour['wavePeriod']['meteo'],
                                    'wind_dir': hour['windDirection']['noaa'],
                                    'wind_speed ': hour['windSpeed']['noaa'],

                                    })

            new_df = pd.DataFrame(data_output)
            new_df.to_csv('new_file.csv')

# modify the DataFrame, so it can be plotted correctly by plotly

            df = pd.read_csv('new_file.csv')
            df.time = pd.to_datetime(df.time)

            wave_height_dif = df.wave_hei - df.swell_height
            df['wave_height_dif'] = wave_height_dif

            df['hour'] = df['time'].dt.hour

# getting the current time of the requested spot (!= necessarily the user location)

            utc_dt = datetime.now(timezone.utc)
            local_time = utc_dt.astimezone().isoformat()
            hours = local_time.split('.')[0]
            today = datetime.strptime(hours, '%Y-%m-%dT%H:%M:%S').date()
            now = datetime.strptime(hours, '%Y-%m-%dT%H:%M:%S').hour

# create a plotly bar chart and adjust the layout properties
# here I decided to use the plotly colorscale option to additionally show the direction of the current,
# since it's value can influence the quality of the waves and the surf experience a lot.
# Stormglass gives the direction coordinates starting from 0° as North
# The direction and speed of the wind and speed of the current still need to be added

            fig = go.Figure(go.Bar(x=df.hour, y=df.swell_height, text=df.swell_height,
                                   textangle=0, textfont_color="red",
                                   marker=dict(color=df.current_dir, colorscale='inferno')),
                            layout=go.Layout(height=800, width=1000))
            fig.add_trace(go.Bar(x=df.hour, y=wave_height_dif, name='Direction of current with north = 0°',
                                 text=df.wave_hei, textangle=0, textfont_color="blue",
                                 marker=dict(color=df.current_dir, colorscale='inferno', showscale=True)))
            fig.add_vline(x=now, line_width=1, line_color="red", name='current hour', annotation_text="current hour")

            fig.update_layout(
                title_text=f"Wave Heights on {today} at {location}",
                barmode='stack',
                yaxis={'title': 'Min and Max Wave Height [m]'},
                xaxis={'type': 'category',
                       'title': 'Time [h]',
                       },
                title_font_size=30,
                yaxis_range=[0, 4],

            )
            fig.write_image(file='static/images/new_plot.png', format='png')

# getting the temperatures for the requested location on the current day (I choose
# 3 values for the air temperature and the mean value of the water temperature since
# these value normally don't vary significantly during the day)

            water_temp = df["water_temp"].mean()

            # air_temp_1 = df.loc[df['hour'] == 6, 'air_temp']
            air_temp_2 = df.loc[df['hour'] == 12, 'air_temp']
            # air_temp_3 = df.loc[df['hour'] == 18, 'air_temp']

            # data1 = [["06 a.m.", water_temp_1, air_temp_1],
            #         ["01 p.m.", water_temp_2, air_temp_2],
            #         ["06 p.m.", water_temp_3, air_temp_3]]

            # col_names = ["Time", "Water temperature", "air temperature"]
            # table = (tabulate(data1, headers=col_names))

            return render_template("forecast.html", water_temp=water_temp, air_temp_2=air_temp_2)
        except KeyError:
            flash("Please choose a city, that is located on a beach.")

# if the requested location is not near a water (e.g. Berlin), the Stormglass request will of course
# throw a KeyError

    return render_template("index.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
