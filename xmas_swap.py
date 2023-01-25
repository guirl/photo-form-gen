from random import randint
from pprint import pprint

names = ["Chris", "David", "Stephen", "Billy", "Katie", "Grace"]
avoid_pairs = [("Chris", "Billy"), ("David", "Katie"), ("Stephen", "Grace")]

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
                if name == remaining_names[target] or (name, target_name) in avoid_pairs or (target_name, name) in avoid_pairs:
                    # print(f"Can't assign {remaining_names[target]} to {name}")
                    found = False
                    assert num_remaining > 2, f"Must have more than two names left, only have {remaining_names}. try again lol"
                else: 
                    found = True
            assignments[name] = target_name
            print(f"assigned {remaining_names[target]} to {name}")
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
print(f"Total number of permutations: {len(permutations)}")
