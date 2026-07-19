import os
import pandas as pd
import openpyxl
from ortools.sat.python import cp_model
players  = []
class ReadFiles:
    def __init__(self, file):
        self.file = file
        df = pd.read_excel(self.file)
        data_rows = df[['Names', 'Positions', 'Ratings']].values.tolist()
        self.dr = data_rows
        players.extend(data_rows)
        print(players)
    def get_data(self):
            return self.dr
class Player:
    def __init__(self, name, pos, rate):
        self.name = name
        self.pos = pos
        self.position = []
        self.rate = int(float(rate) * 10)
        tags = str(pos).split(';')
        for t in tags:
            c_t = t.strip().lower()
            self.position.append(c_t)
        

    def __repr__(self):
         return f"Player({self.name}, {self.pos}, {self.rate})"
    def is_gk(self):
        for p in self.position:
            if(p == 'gk'):
                return True
        return False
    def is_def(self):
        for p in self.position:
            match p:
                case 'cb' |'cdm' |'lb' | 'rb' | 'lwb' | 'rwb':
                    return True
        return False
    def is_atk(self):
        for p in self.position:
            match p:
                case 'st' |'fw' |'lw' | 'rw' | 'cam' | 'cf' | 'att' | 'cm':
                    return True
        return False
        
                

class Team:
    def __init__(self, members, max):
        self.members = []
        self.max = max
    def add_players(self, player):
         if(len(self.members)< self.max):
              self.members.append(player)
    def get_total_ratings(self):
        total = 0
        for m in self.members:
            total += m.rate
        return total
    

class csp_solve:
    def __init__(self, players, config):
        self.players = players
        self.config = config
        string = config.split('-')
        self.teams = []

        for item in string:
            num = int(item)
            self.teams.append(num)
        self.t_num = len(self.teams)
        self.p_num = len(self.players)

        slots = sum(self.teams)
        if slots != self.p_num:
            print("Error: Player count D.N.E team slots")

    def solve(self):
        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = 42  # Deterministic results
        solver.parameters.max_time_in_seconds = 10.0  # Give solver more time
        solver.parameters.log_search_progress = False  # Suppress solver logs
        x = {}
        
        #Builds a 2D matrix for player(rows) and teams(col)
        for i in range(self.p_num):
            for j in range(self.t_num):
                label = f"player_{i}_team_{j}"
                x[i,j] = model.new_bool_var(label)

        # No clones and each slot gets filled
        for i in range(self.p_num):
            player_switch = []
            for j in range(self.t_num):
                player_switch.append(x[i,j])
            model.add(sum(player_switch) == 1)

        # Forces a player on exactly 1 team
        for j in range(self.t_num):
            team_switches = []
            for i in range(self.p_num):
                team_switches.append(x[i,j])
            model.add(sum(team_switches) == self.teams[j])

        # Hard: at most 1 GK per team (no duplicates)
        # Soft: prefer 1 GK per team (penalty if missing, but allows flexibility)
        gk_penalty = 0
        for j in range(self.t_num):
            team_gk = []
            team_atk = []
            team_def = []
            for i in range(self.p_num):
                if self.players[i].is_gk():
                    team_gk.append(x[i,j])
                if self.players[i].is_def():
                    team_def.append(x[i,j])
                if self.players[i].is_atk():
                    team_atk.append(x[i,j])
            
            # Hard: at most 1 GK
            model.add(sum(team_gk) <= 1)
            # Soft: prefer 1 GK (penalty if 0, but not required)
            gk_shortage = model.new_bool_var(f"no_gk_{j}")
            model.add(sum(team_gk) >= 1 - gk_shortage)  # If no GK, shortage=True
            gk_penalty += gk_shortage * 100
            
            model.add(sum(team_def) >= 0)
            model.add(sum(team_atk) >= 0)
        
        # Calculate each teams' total strength and balance it
        team_totals = []
        for j in range(self.t_num):
            total_rate = model.new_int_var(0, 100000, f"total_rate_{j}")
            model.add(total_rate == sum(x[i, j] * self.players[i].rate for i in range(self.p_num)))
            team_totals.append(total_rate)
        
        # Two-stage: First maximize weakest team, then minimize disparity
        max_total = model.new_int_var(0, 100000, "max_total")
        min_total = model.new_int_var(0, 100000, "min_total")

        for total in team_totals:
            model.add(max_total >= total)
            model.add(min_total <= total)

        disparity = model.new_int_var(0, 100000, "disparity")
        model.add(disparity == max_total - min_total)
        
        # Prioritize: minimize disparity first, then GK preference, then maximize weakest team
        model.minimize(disparity * 1000 + gk_penalty - min_total)

        # Solves the model
        status = solver.solve(model)
        status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE" if status == cp_model.FEASIBLE else "UNKNOWN"
        print(f"\nSolver Status: {status_str}")
        print(f"Disparity (min spread): {solver.objective_value}")
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for j in range(self.t_num):
                # Creates all teams
                new_teams = Team(members= [], max= self.teams[j])
                for i in range(self.p_num):
                    if solver.value(x[i,j])== 1:
                        new_teams.add_players(self.players[i])
                print(f"\nTEAM {j+1} (Max Size: {new_teams.max})")
                print(f"Players: {new_teams.members}")
                print(f"Combined Strength: {new_teams.get_total_ratings()}")
        else:
            print("Error something happened to the model!")



script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, 'Players.xlsx')
reader = ReadFiles(file_path)
raw_rows = reader.get_data()
player_pool = []
for rows in raw_rows:
    name,pos,rate = rows
    player_pool.append(Player(name, pos, rate))
total_players = len(player_pool)
while True:
    print(f"Player Number: {total_players}, enter correct sequnce of numbers")
    user = input(str("Enter team sizes, seperated by dashes(4-4-4-4 or 5-5-6): "))
    sizes_list = user.split('-')
    parsed = []
    for s in sizes_list:
        parsed.append(int(s))
    if sum(parsed) == total_players:
        engine = csp_solve(player_pool, user)
        engine.solve()
        break