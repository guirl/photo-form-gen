from random import randint
from pprint import pprint

names = ["C", "D", "S", "B", "K", "G", "J", "W", "L"]
avoid_pairs = [("C", "B"), ("D", "K"), ("S", "G"), ("J", "W")]
last_year = [("C", "D"), ("D", "G"), ("S", "K"), ("B", "S"), ("K", "C"), ("G", "B")]

THIS_IS_SILLY = 1000

permutations = []

more_assignments = True
attempts = 0
while more_assignments:
    assignments = {}
    print(f"Starting a new run!")
    try:
        for name in names:
            remaining_names = [name for name in names if name not in assignments.values()]
            # print(f"remaining names: {remaining_names}")
            found = False
            while not found:
                num_remaining = len(remaining_names)
                target = randint(0, num_remaining - 1)
                target_name = remaining_names[target]
                # print(f"Trying target {target}")
                if name == remaining_names[target] \
                    or (name, target_name) in avoid_pairs \
                    or (target_name, name) in avoid_pairs \
                    or (name, target_name) in last_year:
                    # print(f"Can't assign {remaining_names[target]} to {name}")
                    found = False
                    assert num_remaining > 2, f"Must have more than two names left, only have {remaining_names}. try again lol"
                else: 
                    found = True
            assignments[name] = target_name
            print(f"{name} buys for {remaining_names[target]}")
        if assignments not in permutations:
            permutations.append(assignments)
            attempts = 0
        else:
            attempts += 1
            if attempts > THIS_IS_SILLY:
                more_assignments = False
    except AssertionError as e:
        print(f"Ran into a deadlock, trying again! {e}")
    # pprint(assignments)
total_permutations = len(permutations)
print(f"Total number of permutations: {total_permutations}")
which_permutation = randint(0, total_permutations - 1)
print(f"Final choice: permutation {which_permutation}. assignments:\n{permutations[which_permutation]}")
