#!/usr/bin/python3
# flake8: noqa
"""
Workshop Plan Generator

This script generates optimal workshop plans based on various constraints:
- Workshop availability in specific blocks
- User attendance windows
- Lecturer availability
- Workshop preferences

Usage:
  python3 make_plan.py data.json                  # Generate a new plan
  python3 make_plan.py data.json [[1,2],[3,4]]    # Load and evaluate an existing plan
"""

import random
from copy import deepcopy
import json
import sys
import time
from datetime import datetime

if len(sys.argv) not in [2, 3]:
    print("Usage {file} data.json".format(file=sys.argv[0]))
    print("Usage {file} data.json [[1, 2, 3], [4, 5, 6]]".format(file=sys.argv[0]))
    sys.exit(1)

# Constants
NUM_BLOCKS = 6                      # Total number of workshop blocks
DATE_FORMAT = "%Y-%m-%d"           # Format for parsing date strings
DEFAULT_MAX_ITERATIONS = 10**5     # Default max iterations for optimization
DEFAULT_TIME_LIMIT_SECONDS = 10    # Default time limit for optimization in seconds
PROGRESS_REPORT_INTERVAL = 10**4   # How often to report progress during optimization
NUM_INITIAL_PLANS = 1000           # Number of initial random plans to generate
NUM_MUTATIONS_PER_IMPROVE = 5      # Maximum number of mutations per improvement step

def load_data(filename):
    """Load workshop and user data from JSON file."""
    with open(filename) as f:
        return json.load(f)

# Reads data in format of dataForPlan.
data = load_data(sys.argv[1])

# Create workshop lookup dictionary by workshop ID
workshops = {ws['wid']: ws for ws in data['workshops']}
workshops_per_block = len(workshops) / NUM_BLOCKS  # Average workshops per block

# Scoring penalties
PENALTY_DISALLOWED_BLOCK = 10**4       # Penalty for placing workshop in disallowed block
PENALTY_WRONG_WORKSHOPS_PER_BLOCK = 10**3  # Penalty for uneven workshop distribution
PENALTY_LECTURER_COLLISION = 10**6     # Penalty for lecturer scheduled in multiple workshops

verbose = False

# Block dates for 2023 WWW workshops
BLOCK_0_1_START = datetime(2023, 7, 26)
BLOCK_0_1_END = datetime(2023, 7, 28)
BLOCK_2_3_START = datetime(2023, 7, 30)
BLOCK_2_3_END = datetime(2023, 8, 1)
BLOCK_4_5_START = datetime(2023, 8, 3)
BLOCK_4_5_END = datetime(2023, 8, 5)

def initialize_users(user_data):
    """Initialize user data with attendance blocks and workshop participation sets."""
    users_dict = {u['uid']: u for u in user_data}
    
    for uid in users_dict:
        # Initialize sets for tracking participation and available blocks
        users_dict[uid]['part'] = set()  # Workshops the user participates in
        users_dict[uid]['blocks'] = set()  # Blocks the user can attend
        
        # Parse arrival and departure dates
        arrive = datetime.strptime(users_dict[uid]['start'], DATE_FORMAT)
        depart = datetime.strptime(users_dict[uid]['end'], DATE_FORMAT)
        
        # Remove original date strings as they're no longer needed
        del users_dict[uid]['start']
        del users_dict[uid]['end']
        
        # Assign blocks based on user attendance dates
        if arrive <= BLOCK_0_1_START and depart >= BLOCK_0_1_END:
            users_dict[uid]['blocks'].add(0)
            users_dict[uid]['blocks'].add(1)
        if arrive <= BLOCK_2_3_START and depart >= BLOCK_2_3_END:
            users_dict[uid]['blocks'].add(2)
            users_dict[uid]['blocks'].add(3)
        if arrive <= BLOCK_4_5_START and depart >= BLOCK_4_5_END:
            users_dict[uid]['blocks'].add(4)
            users_dict[uid]['blocks'].add(5)
            
    return users_dict

# Initialize users with their attendance blocks
users = initialize_users(data['users'])

def process_participation(participation_data, users_dict, workshop_ids):
    """Process participation data to track which users are participating in which workshops."""
    # Add workshop participation based on explicit participation records
    for part in participation_data:
        if part['wid'] in workshop_ids:
            users_dict[part['uid']]['part'].add(part['wid'])
    
    # Lecturers automatically participate in their own workshops
    for ws in workshops.values():
        for lec_uid in ws['lecturers']:
            users_dict[lec_uid]['part'].add(ws['wid'])

# Create list of workshop IDs for easy access
wid_list = list(workshops.keys())

# Process participation data
process_participation(data['participation'], users, wid_list)


class Plan(object):
    """Represents a workshop plan with workshops assigned to specific blocks.
    
    A plan consists of:
    - blocks: A list of sets, where each set contains workshop IDs for that block
    - workshops: A dictionary mapping workshop IDs to their assigned block
    """
    def __init__(self, tab=None):
        """Initialize a new plan, either empty or from an existing plan table.
        
        Args:
            tab: Optional list of lists representing existing block assignments
        """
        self.workshops = dict()  # Maps workshop ID to block number
        if tab is None:
            # Create empty blocks
            self.blocks = [set() for i in range(NUM_BLOCKS)]
        else:
            # Initialize from existing plan
            self.blocks = [set() for i in range(NUM_BLOCKS)]
            for i in range(NUM_BLOCKS):
                for wid in tab[i]:
                    self.add(i, wid)
    
    def tab(self):
        """Convert the plan to a tabular format (list of lists).
        
        Returns:
            List of lists where each inner list contains workshop IDs for a block
        """
        tab = []
        for i in range(NUM_BLOCKS):
            tab.append([])
            for wid in self.blocks[i]:
                tab[i].append(wid)
        return tab
    
    def add(self, block, wid):
        """Add a workshop to a specific block.
        
        Args:
            block: Block number (0-5)
            wid: Workshop ID to add
            
        Raises:
            AssertionError: If block is invalid, workshop doesn't exist,
                           or workshop is already assigned
        """
        assert 0 <= block < NUM_BLOCKS, f"Block must be between 0 and {NUM_BLOCKS-1}"
        assert wid in workshops, f"Workshop {wid} does not exist"
        assert wid not in self.workshops, f"Workshop {wid} already assigned to block {self.workshops.get(wid)}"
        
        self.blocks[block].add(wid)
        self.workshops[wid] = block
    
    def copy(self):
        """Create a deep copy of this plan.
        
        Returns:
            A new Plan instance with the same workshop assignments
        """
        plan = Plan()
        plan.blocks = deepcopy(self.blocks)
        plan.workshops = deepcopy(self.workshops)
        return plan
    
    def mutate(self, wid=None, block=None):
        """Move a workshop to a different block.
        
        This is used during optimization to explore different plan configurations.
        
        Args:
            wid: Optional workshop ID to move, random if None
            block: Optional target block, random if None
        """
        # Select a workshop to move (either specified or random)
        if wid is None:
            random_wid = random.choice(wid_list)
        else:
            random_wid = wid
            
        # Select a target block (either specified or random)
        if block is None:
            random_block = random.randint(0, NUM_BLOCKS - 1)
        else:
            random_block = block
            
        # Make sure we're moving to a different block
        while random_block == self.workshops[random_wid]:
            random_block = random.randint(0, NUM_BLOCKS - 1)
        
        # Remove from current block
        self.blocks[self.workshops[random_wid]].remove(random_wid)
        del self.workshops[random_wid]
        
        # Add to new block
        self.add(random_block, random_wid)
    
    def mutate_by_exchange(self):
        """Swap the blocks of two randomly selected workshops.
        
        This is used during optimization to explore different plan configurations.
        """
        # Select two random workshops
        random_wid1 = random.choice(wid_list)
        random_wid2 = random.choice(wid_list)
        
        # Get their current blocks
        random_block1 = self.workshops[random_wid1]
        random_block2 = self.workshops[random_wid2]
        
        # Swap their blocks
        self.mutate(random_wid1, random_block2)
        self.mutate(random_wid2, random_block1)
        
    @staticmethod
    def make_random_plan():
        """Create a new plan with workshops randomly assigned to blocks.
        
        Returns:
            A new Plan instance with random workshop assignments
        """
        plan = Plan()
        for wid in workshops:
            plan.add(random.randint(0, NUM_BLOCKS - 1), wid)
        return plan
    
    def describe(self):
        for uid in users:
            printed_user_already = False
            for block in users[uid]['blocks']:
                wids_on_block_for_user = [wid for wid in users[uid]['part'] if wid in self.blocks[block]]
                if len(wids_on_block_for_user) > 1:
                    if printed_user_already is False:
                        print(" *", users[uid]['name'], " registered for", len(users[uid]['part']), "workshops")
                        printed_user_already = True
                    print("  ", len(wids_on_block_for_user), "collisions:", [workshops[wid]['name'] for wid in wids_on_block_for_user])
                    
        
        collision_sum = 0
        collision_user_sum = 0
        # Print details for each block
        for block in range(NUM_BLOCKS):
            print("BLOCK", block)
            for wid in self.blocks[block]:
                participants_willing_to = 0
                participants_today = 0
                collisions = 0
                collision_users = 0
                for uid in users:
                    if wid in users[uid]['part']:
                        participants_willing_to += 1
                        if block in users[uid]['blocks']:
                            participants_today += 1
                            collided = False
                            for wid2 in self.blocks[block]:
                                if wid2 == wid:
                                    continue
                                if wid2 in users[uid]['part']:
                                    if collided is False:
                                        collision_users += 1
                                        collision_user_sum += 1
                                        collided = True
                                    collisions += 1
                                    collision_sum += 1
                print(" *", wid, workshops[wid]['name'], "-", [users[lid]['name'] for lid in workshops[wid]['lecturers']][0])
                print("   participants today/willing:", participants_today, "/", participants_willing_to)
                print("   collisions / user collisions:", collisions, "/", collision_users)
            print("-------")
        print("colisions total = {sum}, colision users total = {users}".format(sum=collision_sum, users=collision_user_sum))

    def evaluate(self, verbose=False):
        all_wids = set()
        all_lecturer_uids = set()
        for widset in self.blocks:
            all_wids.update(widset)
        
        for wid in wid_list:
            if wid not in all_wids:
                raise KeyError("There is no wid", wid, all_wids)
        
        points = 0
        points_col = 0
        
        for wid in all_wids:
            for lec_uid in workshops[wid]['lecturers']:
                all_lecturer_uids.add(lec_uid)
                if self.workshops[wid] not in users[lec_uid]['blocks']:
                    if verbose:
                        print("COLLISION OF LECTURER")
                        print("\tlec_uid={uid} wid={wid}".format(uid=lec_uid, wid=wid))
                    points -= 10**6

        for wid in all_wids:
            for disallowed_block in workshops[wid].get('disallowed_blocks', []):
                if wid in self.blocks[disallowed_block]:
                    if verbose:
                        print("DISALLOWED BLOCK")
                        print("\twid={wid} block={block}".format(wid=wid, block=disallowed_block), workshops[wid]['name'])
                    points -= PENALTY_DISALLOWED_BLOCK

        for block in self.blocks:
            lectures_in_block = set()
            for wid in block:
                for lec_uid in workshops[wid]['lecturers']:
                    if lec_uid in lectures_in_block:
                        if verbose:
                            print("LECTURER IN MORE THAN ONE WORKSHOP")
                            print("\tuid={uid} wid={wid}".format(uid=lec_uid, wid=wid))
                        points -= PENALTY_LECTURER_COLLISION
                    lectures_in_block.add(lec_uid)

        for block in self.blocks:
            if abs(workshops_per_block - len(block)) > 0.9:
                if verbose:
                    print("WRONG NUMBER OF WORKSHOPS IN BLOCK {block}".format(block=block))
                points -= abs(workshops_per_block - len(block)) * PENALTY_WRONG_WORKSHOPS_PER_BLOCK


        col_counter = {wid:0 for wid in all_wids}
        for uid in (uid for uid in users if uid not in all_lecturer_uids):
            user_blocks = dict()
            for wid in users[uid]['part']:
                if self.workshops[wid] in users[uid]['blocks']:
                    if self.workshops[wid] not in user_blocks:
                        user_blocks[self.workshops[wid]] = []
                    user_blocks[self.workshops[wid]].append(wid)
            for block in user_blocks:
                if len(user_blocks[block]) > 1:
                    for wid in user_blocks[block]:
                        col_counter[wid] += 1
                    
            empty_blocks = min(len(users[uid]['blocks']), len(users[uid]['part'])) - len(user_blocks)
            assert empty_blocks >= 0
            #print(empty_blocks, users[uid]['name'])
            points -= empty_blocks**empty_blocks if empty_blocks>0 else 0
            if empty_blocks > 0:
                if verbose:
                    print(empty_blocks, "EMPTY BLOCKS for", users[uid]['name'])
                    print("\tuid={uid}".format(uid=uid))
            #points += len(user_blocks)
        
        for wid in col_counter:
            points_col -= col_counter[wid]**2
        
        return points * 5 + points_col

def improve_plan(plan, current_score):
    """Improve a plan through random mutations.
    
    Args:
        plan: The Plan object to improve
        current_score: Current score of the plan
        
    Returns:
        Tuple of (improved_plan, improved_score)
    """
    # Create a copy to avoid modifying the original
    improved_plan = plan.copy()
    
    # Apply random mutations
    for _ in range(random.randint(1, NUM_MUTATIONS_PER_IMPROVE)):
        if random.randint(0, 1) == 0:
            improved_plan.mutate()
        else:
            improved_plan.mutate_by_exchange()
            
    # Evaluate the improved plan
    improved_score = improved_plan.evaluate()
    
    # Return the better plan
    if improved_score >= current_score:
        return improved_plan, improved_score
    else:
        return plan, current_score


def optimize_plan(time_limit_seconds=DEFAULT_TIME_LIMIT_SECONDS):
    """Generate and optimize multiple workshop plans.
    
    Args:
        time_limit_seconds: Maximum time to run optimization in seconds
        
    Returns:
        The best Plan object found
    """
    # Generate multiple random plans
    print(f"Generating {NUM_INITIAL_PLANS} initial random plans...")
    plans_and_scores = []
    for _ in range(NUM_INITIAL_PLANS):
        plan = Plan.make_random_plan()
        score = plan.evaluate()
        plans_and_scores.append((plan, score))
    
    # Track the best plan
    best_score = max(score for _, score in plans_and_scores)
    
    # Track optimization progress
    start = time.time()
    last_print_time = start
    iteration = 0
    
    try:
        # Continue improving until time limit or keyboard interrupt
        while time.time() - start < time_limit_seconds:
            # Improve each plan
            for i in range(len(plans_and_scores)):
                plans_and_scores[i] = improve_plan(plans_and_scores[i][0], plans_and_scores[i][1])
                
                # Update best score if needed
                if plans_and_scores[i][1] > best_score:
                    best_score = plans_and_scores[i][1]
                    
                # Print progress periodically
                if verbose and iteration % PROGRESS_REPORT_INTERVAL == 0:
                    print(f"Iteration {iteration}, Best score: {best_score}")
                    
                iteration += 1
                
            # Print progress every second
            if time.time() - last_print_time > 1.0:
                print(f"Best score so far: {best_score}")
                last_print_time = time.time()
                
    except KeyboardInterrupt:
        print("Optimization interrupted by user")
    
    # Find the best plan
    best_plan = None
    for plan, score in plans_and_scores:
        if score == best_score:
            best_plan = plan
            break
            
    return best_plan, best_score

def display_results(plan, score):
    """Display the results of plan optimization.
    
    Args:
        plan: The best Plan object found
        score: The score of the best plan
    """
    print("Best score", score)
    print("Plan")
    plan.describe()
    plan.evaluate(verbose=True)
    print("JSON:")
    print(json.dumps(plan.tab()))

def evaluate_existing_plan(plan_json):
    """Evaluate an existing plan provided as a JSON string.
    
    Args:
        plan_json: JSON string representing a plan
    """
    plan = Plan(json.loads(plan_json))
    plan.describe()
    plan.evaluate(verbose=True)
    sys.exit(0)

def main():
    """Main entry point for the script.
    
    Usage:
      python3 make_plan.py data.json                  # Generate a new plan
      python3 make_plan.py data.json [[1,2],[3,4]]    # Load and evaluate an existing plan
    """
    # Check if we have the right number of arguments
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} data.json [plan_json]")
        sys.exit(1)
        
    # Generate a new plan if only data file is provided
    if len(sys.argv) == 2:
        best_plan, best_score = optimize_plan(DEFAULT_TIME_LIMIT_SECONDS)
        display_results(best_plan, best_score)
    # Evaluate an existing plan if plan JSON is also provided
    elif len(sys.argv) > 2:
        evaluate_existing_plan(sys.argv[2])
    else:
        print("Invalid number of arguments")

if __name__ == "__main__":
    main()
