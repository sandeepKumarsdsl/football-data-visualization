import requests
import json
import sys
import pandas as pd
import numpy as np


class Game:
    """
    Game object with json_file attribute, which is the event data for
    a game as a JSON file (from Statsbomb public data) pre-loaded into python.
    """

    def __init__(self, json_file):
        self.json_file = json.loads(json_file)

    def get_shots_for_game(self):
        """
        Parses through Game object's json_file and returns a data frame
        containing all shots taken in that game with several features related
        to the shots.

        Arguments
        ---------
        None

        Returns
        -------
        pandas.DataFrame
            - Data frame containing shots and features
        """
        # features for each shot, which will be the columns of our data frame
        feature_list = ["shot id", "team_id", "team_name", "player_id",
                        "player_name", "play pattern", "x start location",
                        "y start location", "duration", "outcome", "technique",
                        "first time", "x gk position", "y gk position",
                        "type of shot", "num opponents within 5 yards",
                        "num opponents between shot and goal", "statsbomb xg"]

        features = []

        for events in self.json_file:

            if events['type']['name'] == 'Shot':

                # get data for first 8 features
                shot_id = events['id']
                team_id = events['possession_team']['id']
                team_name = events['possession_team']['name']
                player_id = events['player']['id']
                player_name = events['player']['name']
                x_start = events['location'][0]
                y_start = events['location'][1]
                play_pattern = events['play_pattern']['name']
                duration = events['duration']
                outcome = events['shot']['outcome']['name']
                technique = events['shot']['technique']['name']
                type_shot = events['shot']['type']['name']
                xg = events['shot']['statsbomb_xg']

                # check if json shot has a first_time attribute,
                # if not set first_time to False
                if 'first_time' in events['shot']:
                    first_time = events['shot']['first_time']
                else:
                    first_time = False

                # check if shot has a freeze_frame dictionary
                if "freeze_frame" in events["shot"]:

                    num_opponents_5_yards = 0
                    num_opponents_between_goal = 0

                    for player in events["shot"]["freeze_frame"]:
                        x_player = player['location'][0]
                        y_player = player['location'][1]

                        # count how many opponents were within 5yards of player
                        # when shot was taken
                        x_dist = (x_start - x_player)**2
                        y_dist = (y_start - y_player)**2
                        if (x_dist+y_dist) <= 25 and (not player['teammate']):
                            if (player['position']['name'] != 'Goalkeeper'):
                                num_opponents_5_yards += 1

                        # count how many opponents were between shot and goal
                        if (not player['teammate']) and \
                           (player['position']['name'] != 'Goalkeeper'):
                            if self.check_player_btwn_shot_and_goal(x_start,
                                                                    y_start,
                                                                    x_player,
                                                                    y_player):
                                num_opponents_between_goal += 1

                        # get position of opponent's goalkeeper
                        if (player['position']['name'] == 'Goalkeeper') and \
                           (not player['teammate']):
                            x_gk_pos = player['location'][0]
                            y_gk_pos = player['location'][1]

                # if there is no freeze frame, assume goalkeeper is at
                # center of goal, and 0 opponenets around shot location
                else:
                    num_opponents_between_goal = 0
                    num_opponents_5_yards = 0
                    x_gk_pos = 120
                    y_gk_pos = 40

                features.append([shot_id, team_id, team_name, player_id,
                                 player_name, play_pattern, x_start, y_start,
                                 duration, outcome, technique, first_time,
                                 x_gk_pos, y_gk_pos, type_shot,
                                 num_opponents_5_yards,
                                 num_opponents_between_goal, xg])

        # create data frame
        shot_df = pd.DataFrame(features,
                               columns=feature_list).set_index("shot id")

        self.shot_df = shot_df

        return shot_df

    def check_player_btwn_shot_and_goal(self, xshot, yshot, xplayer, yplayer):
        """
        Helper function for get_shots_for_game().
        Checks whether a player in a statsbomb freeze frame is between the shot
        location, and the two lines connecting the shot location to the posts.
        See here for coordinate specifications:
        https://github.com/statsbomb/open-data/blob/master/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf

        Arguments:
        ----------
        xshot : float
            - x-location of shot
        yshot : float
            - y-location of shot
        xplayer : float
            - x-location of player
        yplayer : float
            - y-location of player
        """
        x_diff = xplayer - xshot

        if 120 - xshot == 0:
            return False

        slope_1 = (36 - yshot) / (120 - xshot)
        slope_2 = (44 - yshot) / (120 - xshot)

        btwn = (yshot + slope_1*x_diff) < yplayer < (yshot + slope_2*x_diff)
        return (x_diff >= 0) and btwn

    def get_events_for_game(self):
        """
        Parses through Game object's json_file and returns a data frame
        containing all all shots, passes, ball receipts and carries performed
        in that game with several features related to those events.
            - eventid
            - x start location
            - y start location
            - x end location (-1 if event is a shot)
            - y end location (-1 if event is a shot)
            - xg (-1 if event is not a shot)

        Arguments
        ---------
        None

        Returns
        -------
        pandas.DataFrame
            - data frame containing all shots, passes, ball receipts and
            carries performed in the specified game with several features
            related to those events
        """

        feature_list = ["event id", "time", "event name", "team_id",
                        "team_name", "player_id", "player_name",
                        "x start location", "y start location",
                        "x end location", "y end location",
                        "statsbomb xg", "related events"]

        features = []
        event_list = ["Pass", "Ball Receipt*", "Carry", "Shot"]
        for events in self.json_file:
            if events['type']['name'] in event_list:
                event_id = events['id']
                time = events['timestamp']
                event_name = events['type']['name'].lower()
                team_id = events['possession_team']['id']
                team_name = events['possession_team']['name']
                player_id = events['player']['id']
                player_name = events['player']['name']
                x_start = events['location'][0]
                y_start = events['location'][1]

                if event_name == "shot":
                    x_end = -1
                    y_end = -1
                    xg = events[event_name]["statsbomb_xg"]

                elif event_name == "ball receipt*":
                    x_end = -1
                    y_end = -1
                    xg = -1

                else:
                    x_end = events[event_name]["end_location"][0]
                    y_end = events[event_name]["end_location"][1]
                    xg = -1

                if "related_events" in events.keys():
                    related = events["related_events"]
                    is_pass = (event_name == "pass")
                    if is_pass and "assisted_shot_id" in events["pass"].keys(): # noqa
                        related.append(events["pass"]["assisted_shot_id"])
                else:
                    related = None

                features.append([event_id, time, event_name, team_id,
                                 team_name, player_id, player_name,
                                 x_start, y_start, x_end, y_end,
                                 xg, related])

        events_df = pd.DataFrame(features,
                                 columns=feature_list).set_index("event id")

        self.event_df = events_df

        return events_df


def fetch_matches_for_season(competition_id, season_id, verbose=True):
    """
    Takes a competition id and season id as specified by Statsbomb,
    and returns a dictionary maping game id's to the game's
    event level JSON data.

    Arguments
    ---------
    competition_id : int
        - competition id as specified by Statsbomb
        See here: https://github.com/statsbomb/open-data/blob/master/data/competitions.json # noqa
    season_id : int
        - season id as specified by Statsbomb
        See here: https://github.com/statsbomb/open-data/blob/master/data/competitions.json # noqa

    Returns
    -------
    dict
        - mapping of game id's to a 'Game' object with a
        json_file attribute (the event data for that game as a JSON file).

    Examples
    --------
    fetch_matches_for_season(11, 21)
    """
    # Get webpage html for competitions.json
    comp_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json" # noqa
    req = requests.get(comp_url).text
    # Convert webpage to json format
    competitions_statsbomb = json.loads(req)
    comp_id_list = np.unique([x['competition_id'] for x in competitions_statsbomb]) # noqa
    season_id_list = np.unique([x['season_id'] for x in competitions_statsbomb]) # noqa
    assert competition_id in comp_id_list, \
        f"""competition id must be one of {comp_id_list}.
        See here: https://github.com/statsbomb/open-data/blob/master/data/competitions.json" """ # noqa
    assert season_id in season_id_list, \
        f"""season id must be one of {season_id_list}.
        See here: https://github.com/statsbomb/open-data/blob/master/data/competitions.json" """ # noqa

    base = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches" # noqa
    req = requests.get(base + f"/{competition_id}" + f"/{season_id}.json").text
    season_json = json.loads(req)

    game_nums = [game['match_id'] for game in season_json]

    base_url_string = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/" # noqa
    game_num_dict = {}
    if verbose:
        print(f"Fetching matches for season_id {season_id} " +
              f"of competition_id {competition_id}...")
    for i, game_num in enumerate(game_nums):
        game_num_dict[game_num] = Game(requests.get(base_url_string +
                                                    str(game_num) +
                                                    ".json").text)
        if verbose:
            sys.stdout.write('\r')
            sys.stdout.write(f"[%-{len(game_nums)-1}s] %d%%"
                             % ('='*i, (100/(len(game_nums)-1))*i))
            sys.stdout.flush()
    if verbose:
        print("")

    return game_num_dict


def fetch_seasons_for_league(competition_id, verbose=True):
    """
    Takes a competition id as specified by Statsbomb, and returns a dictionary
    mapping season id's to inner dictionaries, which themselves map game id's
    to the game's event level JSON data.

    Arguments
    ---------
    competition_id : int
        - competition id as specified by Statsbomb
        See here: https://github.com/statsbomb/open-data/blob/master/data/competitions.json # noqa

    Returns
    -------
    dict of dicts
        - mapping of season id's to inner dictionaries, which themselves map
        game id's to a 'Game' object with a json_file attribute
        (the event data for that game as a JSON file).

    Examples
    --------
    fetch_seasons_for_league(11)

    """
    # Get webpage html for competitions.json
    comp_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json" # noqa
    req = requests.get(comp_url).text
    # Convert webpage to json format
    competitions_statsbomb = json.loads(req)

    comp_id_list = np.unique([x['competition_id'] for x in competitions_statsbomb]) # noqa
    assert competition_id in comp_id_list, \
        f"""competition id must be one of {comp_id_list}.
        See here: https://github.com/statsbomb/open-data/blob/master/data/competitions.json" """ # noqa

    all_seasons_id = {}
    for comps in competitions_statsbomb:
        if comps['competition_id'] == competition_id:
            season_id = comps['season_id']
            season_name = comps['season_name']

            all_seasons_id[season_name] = season_id

    all_games_by_seasons = {}
    print(f"Matches will be fetched for {len(all_seasons_id)} seasons.")
    for season_name, season_id in all_seasons_id.items():
        season = fetch_matches_for_season(competition_id,
                                          season_id,
                                          verbose=verbose)
        all_games_by_seasons[season_name] = season

    print("\n\nDone")

    return all_games_by_seasons


def get_shots_for_season(season_dict):
    """
    Fetches shot data frame for all shots taken over an entire season.

    Arguments
    ---------
    season_dict : dict
        - mapping of game id's to a 'Game' object with a
        json_file attribute (the event data for that game as a JSON file).
        Should be the output of the fetch_matches_for_season() function.

    Returns
    -------
    pandas.DataFrame
        - Data frame containing shots and features

    Examples
    --------
    season_11_37 = fetch_matches_for_season(11, 37)
    get_shots_for_season(season_11_37)

    """
    total_shot_df = pd.DataFrame()

    for game_id, game_obj in season_dict.items():
        shot_df = game_obj.get_shots_for_game()
        shot_df["game_id"] = game_id
        total_shot_df = total_shot_df.append(shot_df)

    return total_shot_df


def get_shots_for_league(league_dict):
    """
    Fetches shot data frame for all shots taken in a league over many seasons.

    Arguments
    ---------
    league_dict : dict of dicts
        - maps season id's to inner dictionaries, which themselves map 'Game'
        object with a json_file attribute (the event data for that game as a
        JSON file).
        Should be the output of fetch_seasons_for_league().

    Returns
    -------
    pandas.DataFrame
        - Data frame containing shots and features

    Examples
    --------
    league_11 = fetch_seasons_for_league(11)
    get_shots_for_league(league_11)
    """
    total_shot_df = pd.DataFrame()

    for keys, values in league_dict.items():
        shot_df = get_shots_for_season(values)
        shot_df["season_id"] = keys
        total_shot_df = total_shot_df.append(shot_df)
        print("Getting shots for " + keys)

    print("Done.")

    return total_shot_df


def draw_pitch(axis, rotate=False):
    """
    Plots the lines of a soccer pitch using matplotlib.

    Arguments
    ---------
    axis : matplotlib.axes._subplots.AxesSubplot
        - matplotlib axis object on which to plot shot freeze frame
    rotate : bool
        - if set to True, pitch is horizontal,
        default to False

    Returns
    -------
    None
    """
    line_width = 4
    alpha = 0.5
    r = 10

    line_coords = [[[0, 0], [0, 120]], [[0, 80], [120, 120]],
                   [[80, 80], [120, 0]], [[0, 80], [0, 0]],
                   [[0, 80], [60, 60]], [[18, 18], [0, 18]],
                   [[18, 62], [18, 18]], [[62, 62], [0, 18]],
                   [[30, 30], [0, 6]], [[30, 50], [6, 6]], [[50, 50], [0, 6]],
                   [[18, 18], [120, 102]], [[18, 62], [102, 102]],
                   [[62, 62], [102, 120]], [[30, 30], [120, 114]],
                   [[30, 50], [114, 114]], [[50, 50], [120, 114]]]

    if not rotate:
        for lines in line_coords:
            axis.plot(lines[0], lines[1], color='grey',
                      linewidth=line_width, alpha=alpha)

        theta1 = np.linspace(0, 2*np.pi, 100)
        theta2 = np.linspace(0.65, 2.47, 100)
        theta3 = np.linspace(3.8, 5.6, 100)
        x1 = r*np.cos(theta1) + 40
        x2 = r*np.sin(theta1) + 60
        x3 = r*np.cos(theta2) + 40
        x4 = r*np.sin(theta2) + 12
        x5 = r*np.cos(theta3) + 40
        x6 = r*np.sin(theta3) + 108

        axis.plot(x1, x2, color='grey', linewidth=line_width,
                  alpha=alpha)
        axis.plot(x3, x4, color='grey', linewidth=line_width,
                  alpha=alpha)
        axis.plot(x5, x6, color='grey', linewidth=line_width,
                  alpha=alpha)

    else:
        for lines in line_coords:
            axis.plot([-(lines[1][0]-40) + 80, -(lines[1][1]-40) + 80],
                      [lines[0][0], lines[0][1]], color='grey',
                      linewidth=line_width, alpha=alpha)

        theta1 = np.linspace(0, 2*np.pi, 100)
        theta2 = np.linspace(5.4, 7.2, 100)
        theta3 = np.linspace(2.2, 4, 100)
        x1 = r*np.cos(theta1) + 60
        x2 = r*np.sin(theta1) + 40
        x3 = r*np.cos(theta2) + 12
        x4 = r*np.sin(theta2) + 40
        x5 = r*np.cos(theta3) + 108
        x6 = r*np.sin(theta3) + 40

        axis.plot(x1, x2, color='grey', linewidth=line_width,
                  alpha=alpha)
        axis.plot(x3, x4, color='grey', linewidth=line_width,
                  alpha=alpha)
        axis.plot(x5, x6, color='grey', linewidth=line_width,
                  alpha=alpha)

    return axis


def plot_shot_freeze_frame(game, shot_id, axis):
    """
    Plots shot freeze frame in Game object shot_df
    including player and ball locations.

    Arguments
    ----------
    game : Game
        - game object
    shot_id : string
        - shot_id of shot to plot. Must be a valid index in game object's
        shot data frame
    axis : matplotlib.axes._subplots.AxesSubplot
        - matplotlib axis object on which to plot shot freeze frame

    Returns
    -------
    matplotlib.axes._subplots.AxesSubplot
        - axis object on which plot was produced
    """
    assert "shot_df" in dir(game), "Game object must have a shot data" + \
                                   "frame. Call game.get_shots_for_game()"
    assert shot_id in game.shot_df.index, "Cannot find specified shot_id" + \
                                          "in this game's shot data frame"

    draw_pitch(axis=axis, rotate=True)

    gk_x = 120
    gk_y = 40
    player_pos_list_x = []
    player_pos_list_y = []
    x_shot = 0
    y_shot = 0

    for events in game.json_file:
        if events['id'] == shot_id:
            x_shot = events['location'][0]
            y_shot = events['location'][1]

            if "freeze_frame" in events["shot"]:
                for players in events['shot']['freeze_frame']:
                    if (not players['teammate']):
                        player_pos_list_x.append(players['location'][0])
                        player_pos_list_y.append(players['location'][1])

                    if (players['position']['name'] == 'Goalkeeper') and \
                       (not players['teammate']):
                        gk_x = players['location'][0]
                        gk_y = players['location'][1]

    axis.scatter(player_pos_list_x, player_pos_list_y)
    axis.scatter(x_shot, y_shot, s=100)
    axis.scatter(gk_x, gk_y, s=100, color='blue')
    axis.plot([x_shot, 120], [y_shot, 36], color='red', linestyle='--')
    axis.plot([x_shot, 120], [y_shot, 44], color='red', linestyle='--')

    return axis


def plot_event(game, event_id, axis):
    """
    Plots event in Game object event data frame.

    Arguments
    ---------
    game : Game
        - game object
    eventid : string
        - event_id of event to plot. Must be a valid index in game object's
        event data frame
    axis (matplotlib.axes._subplots.AxesSubplot)
        - matplotlib axis on which to plot event

    Returns:
    --------
    matplotlib.axes._subplots.AxesSubplot
        - axis object on which plot was produced
    """
    assert "event_df" in dir(game), "Game object must have an event data" + \
                                    "frame. Call game.get_events_for_game()"
    assert event_id in game.event_df.index, "Can't find specified event" + \
                                            "in this game's event data frame"

    event_type = game.event_df.loc[event_id]["event name"]
    x1 = game.event_df.loc[event_id]["x start location"]
    x2 = game.event_df.loc[event_id]["x end location"]
    y1 = game.event_df.loc[event_id]["y start location"]
    y2 = game.event_df.loc[event_id]["y end location"]
    if event_type == "pass":
        axis.arrow(x1, y1, dx=x2-x1, dy=y2-y1, head_width=2, head_length=2)
    elif event_type == "carry":
        axis.plot([x1, x2], [y1, y2], linestyle="--", color="black")
    elif event_type == "shot":
        if "shot_df" in dir(game):
            plot_shot_freeze_frame(game, event_id, axis)
        else:
            axis.scatter(x1, y1, marker="X", s=200)
    elif event_type == "ball receipt*":
        axis.scatter(x1, y1, marker="*", s=200)

    return axis