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
import argparse
from datetime import datetime

# Constants
NUM_BLOCKS = 6                      # Total number of workshop blocks
DATE_FORMAT = "%Y-%m-%d"           # Format for parsing date strings
DEFAULT_MAX_ITERATIONS = 10**5     # Default max iterations for optimization
DEFAULT_TIME_LIMIT_SECONDS = 10    # Default time limit for optimization in seconds
# Default number of initial random plans to generate
DEFAULT_NUM_INITIAL_PLANS = 1000
DEFAULT_TOP_PLANS = 1              # Default number of top plans to display
# How often to report progress during optimization
PROGRESS_REPORT_INTERVAL = 10**4
# Maximum number of mutations per improvement step
NUM_MUTATIONS_PER_IMPROVE = 5


def load_data(filename):
    """Load workshop and user data from JSON file.

    Args:
        filename: Path to the JSON file

    Returns:
        Loaded data as a dictionary
    """
    with open(filename) as f:
        return json.load(f)


# Scoring penalties
# Penalty for placing workshop in disallowed block
PENALTY_DISALLOWED_BLOCK = 10**4
# Penalty for uneven workshop distribution
PENALTY_WRONG_WORKSHOPS_PER_BLOCK = 10**3
# Penalty for lecturer scheduled in multiple workshops
PENALTY_LECTURER_COLLISION = 10**6

# Block dates for 2023 WWW workshops
BLOCK_0_1_START = datetime(2025, 7, 23)
BLOCK_0_1_END = datetime(2025, 7, 25)
BLOCK_2_3_START = datetime(2025, 7, 27)
BLOCK_2_3_END = datetime(2025, 7, 29)
BLOCK_4_5_START = datetime(2025, 7, 31)
BLOCK_4_5_END = datetime(2025, 8, 2)

# Global verbose flag (will be set in main function)
verbose = False


def initialize_users(user_data, blocks_for_lecturers=None):
    """Initialize user data with attendance blocks and workshop participation sets.
    
    Args:
        user_data: List of user dictionaries with uid, name, start, end dates
        blocks_for_lecturers: Optional dictionary mapping lecturer names to allowed blocks
        
    Returns:
        Dictionary of users with initialized blocks and participation sets
        
    Raises:
        ValueError: If a name in blocks_for_lecturers doesn't match any user name
    """
    users_dict = {u['uid']: u for u in user_data}
    
    # Get all user names for validation
    all_user_names = {users_dict[uid]['name'] for uid in users_dict}
    
    # Create a lookup dictionary for lecturers by name if blocks_for_lecturers is provided
    lecturer_blocks = {}
    if blocks_for_lecturers:
        for lecturer in blocks_for_lecturers:
            lecturer_name = lecturer['name']
            
            # Validate that the lecturer name exists in the user data
            if lecturer_name not in all_user_names:
                raise ValueError(f"Error: Lecturer name '{lecturer_name}' in blocks_for_lecturers doesn't match any user name")
                
            lecturer_blocks[lecturer_name] = set(lecturer['allowed-block'])
    
    for uid in users_dict:
        # Initialize sets for tracking participation and available blocks
        users_dict[uid]['part'] = set()  # Workshops the user participates in
        users_dict[uid]['blocks'] = set()  # Blocks the user can attend
        
        # Check if this user is a lecturer with specified blocks
        user_name = users_dict[uid]['name']
        if lecturer_blocks and user_name in lecturer_blocks:
            # Use the specified blocks for this lecturer
            users_dict[uid]['blocks'] = lecturer_blocks[user_name]
            if verbose:
                print(f"Lecturer {user_name} assigned blocks: {users_dict[uid]['blocks']}")
        else:
            # For regular users, use arrival and departure dates
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


def process_participation(participation_data, users_dict, workshop_ids):
    """Process participation data to track which users are participating in which workshops.
    
    Args:
        participation_data: List of participation records with uid and wid
        users_dict: Dictionary of users with initialized blocks and participation sets
        workshop_ids: List of workshop IDs
        
    Returns:
        Dictionary mapping user names to whether they are lecturers
    """
    # Add workshop participation based on explicit participation records
    for part in participation_data:
        if part['wid'] in workshop_ids:
            users_dict[part['uid']]['part'].add(part['wid'])

    # Lecturers automatically participate in their own workshops
    # Track which users are lecturers
    lecturers = {}
    for ws in workshop_ids:
        for lec_uid in workshops[ws]['lecturers']:
            users_dict[lec_uid]['part'].add(ws)
            lecturers[users_dict[lec_uid]['name']] = True
            
    return lecturers


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
        self.workshops = {}  # Maps workshop ID to block number
        if tab is None:
            # Create empty blocks
            self.blocks = [set() for _ in range(NUM_BLOCKS)]
        else:
            # Initialize from existing plan
            self.blocks = [set() for _ in range(NUM_BLOCKS)]
            for block_idx in range(NUM_BLOCKS):
                for wid in tab[block_idx]:
                    self.add(block_idx, wid)

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
                wids_on_block_for_user = [
                    wid for wid in users[uid]['part'] if wid in self.blocks[block]]
                if len(wids_on_block_for_user) > 1:
                    if printed_user_already is False:
                        print(" *", users[uid]['name'], " registered for",
                              len(users[uid]['part']), "workshops")
                        printed_user_already = True
                    print("  ", len(wids_on_block_for_user), "collisions:", [
                          workshops[wid]['name'] for wid in wids_on_block_for_user])

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
                print(" *", wid, workshops[wid]['name'], "-", [users[lid]['name']
                      for lid in workshops[wid]['lecturers']][0])
                print("   participants today/willing:",
                      participants_today, "/", participants_willing_to)
                print("   collisions / user collisions:",
                      collisions, "/", collision_users)
            print("-------")
        print("colisions total = {sum}, colision users total = {users}".format(
            sum=collision_sum, users=collision_user_sum))

    def evaluate(self, verbose=False, return_stats=False):
        """Evaluate the plan quality based on constraints and collisions.

        Args:
            verbose: Whether to print detailed evaluation information
            return_stats: Whether to return statistics about collisions and empty blocks

        Returns:
            If return_stats is False: The plan score (higher is better)
            If return_stats is True: Tuple of (collisions_count, empty_blocks_count)
        """
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
                        print("\tlec_uid={uid} wid={wid}".format(
                            uid=lec_uid, wid=wid))
                    points -= 10**6

        for wid in all_wids:
            for disallowed_block in workshops[wid].get('disallowed_blocks', []):
                if wid in self.blocks[disallowed_block]:
                    if verbose:
                        print("DISALLOWED BLOCK")
                        print("\twid={wid} block={block}".format(
                            wid=wid, block=disallowed_block), workshops[wid]['name'])
                    points -= PENALTY_DISALLOWED_BLOCK

        for block in self.blocks:
            lectures_in_block = set()
            for wid in block:
                for lec_uid in workshops[wid]['lecturers']:
                    if lec_uid in lectures_in_block:
                        if verbose:
                            print("LECTURER IN MORE THAN ONE WORKSHOP")
                            print("\tuid={uid} wid={wid}".format(
                                uid=lec_uid, wid=wid))
                        points -= PENALTY_LECTURER_COLLISION
                    lectures_in_block.add(lec_uid)

        for block in self.blocks:
            if abs(workshops_per_block - len(block)) > 0.9:
                if verbose:
                    print("WRONG NUMBER OF WORKSHOPS IN BLOCK {block}".format(
                        block=block))
                points -= abs(workshops_per_block - len(block)) * \
                    PENALTY_WRONG_WORKSHOPS_PER_BLOCK

        collision_sum = 0
        col_counter = dict.fromkeys(all_wids, 0)
        for uid in (uid for uid in users if uid not in all_lecturer_uids):
            user_blocks = {}
            for wid in users[uid]['part']:
                if self.workshops[wid] in users[uid]['blocks']:
                    if self.workshops[wid] not in user_blocks:
                        user_blocks[self.workshops[wid]] = []
                    user_blocks[self.workshops[wid]].append(wid)
            for block in user_blocks:
                if len(user_blocks[block]) > 1:
                    for wid in user_blocks[block]:
                        col_counter[wid] += 1
                        collision_sum += 1

            empty_blocks = min(len(users[uid]['blocks']), len(
                users[uid]['part'])) - len(user_blocks)
            assert empty_blocks >= 0

            if empty_blocks > 0:
                points -= empty_blocks**empty_blocks
                if verbose:
                    print(empty_blocks, "EMPTY BLOCKS for", users[uid]['name'])
                    print("\tuid={uid}".format(uid=uid))
            # points += len(user_blocks)

        for wid in col_counter:
            points_col -= col_counter[wid]**2

        # Calculate final score
        final_score = points * 5 + points_col

        # Return statistics if requested
        if return_stats:
            # Count empty blocks
            empty_blocks_count = 0
            for uid in users:
                if uid not in all_lecturer_uids:
                    user_blocks = set()
                    for wid in users[uid]['part']:
                        if self.workshops[wid] in users[uid]['blocks']:
                            user_blocks.add(self.workshops[wid])
                    empty_blocks_count += max(
                        0, min(len(users[uid]['blocks']), len(users[uid]['part'])) - len(user_blocks))

            return collision_sum, empty_blocks_count
        else:
            return final_score


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

    # Determine number of mutations to apply (1-5)
    num_mutations = random.randint(1, NUM_MUTATIONS_PER_IMPROVE)

    # Apply random mutations
    for _ in range(num_mutations):
        # 50% chance for each mutation type
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


def optimize_plan(time_limit_seconds=DEFAULT_TIME_LIMIT_SECONDS, num_initial_plans=DEFAULT_NUM_INITIAL_PLANS):
    """Generate and optimize multiple workshop plans.

    Args:
        time_limit_seconds: Maximum time to run optimization in seconds
        num_initial_plans: Number of initial random plans to generate

    Returns:
        List of (plan, score) tuples
    """
    # Generate multiple random plans
    print(f"Generating {num_initial_plans} initial random plans...")
    plans_and_scores = []
    for _ in range(num_initial_plans):
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
                plans_and_scores[i] = improve_plan(
                    plans_and_scores[i][0], plans_and_scores[i][1])

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

    # Sort plans by score (descending)
    sorted_plans = sorted(plans_and_scores, key=lambda x: x[1], reverse=True)

    return sorted_plans


def display_results(plans_and_scores, num_top_plans=DEFAULT_TOP_PLANS):
    """Display the results of plan optimization.

    Args:
        plans_and_scores: List of (plan, score) tuples
        num_top_plans: Number of top plans to display
    """
    # Sort plans by score (descending)
    sorted_plans = sorted(plans_and_scores, key=lambda x: x[1], reverse=True)

    # Display top plans
    for i, (plan, score) in enumerate(sorted_plans[:num_top_plans]):
        if i > 0:
            print("\n" + "=" * 80 + "\n")

        print(f"Plan #{i+1} - Score: {score}")

        if verbose:
            # Full details in verbose mode
            plan.describe()
            plan.evaluate(verbose=True)
        else:
            # Limited details in non-verbose mode
            collisions, empty_blocks = plan.evaluate(
                verbose=False, return_stats=True)
            print(
                f"Total collisions: {collisions}, Total empty blocks: {empty_blocks}")

            # Print block assignments
            for block_num in range(NUM_BLOCKS):
                print(
                    f"BLOCK {block_num}: {', '.join(str(wid) for wid in plan.blocks[block_num])}")

        print("\nJSON:")
        print(json.dumps(plan.tab()))


def evaluate_existing_plan(plan_input):
    """Evaluate an existing plan provided as a JSON string.

    Args:
        plan_input: JSON string or file path representing a plan
    """
    # Try to parse as JSON string first
    try:
        plan_data = json.loads(plan_input)
    except json.JSONDecodeError:
        # If not a valid JSON string, try to load from file
        try:
            with open(plan_input) as f:
                plan_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(
                f"Error: Could not parse plan input as JSON or load from file: {plan_input}")
            sys.exit(1)

    plan = Plan(plan_data)

    if verbose:
        plan.describe()
        plan.evaluate(verbose=True)
    else:
        collisions, empty_blocks = plan.evaluate(
            verbose=False, return_stats=True)
        print(
            f"Total collisions: {collisions}, Total empty blocks: {empty_blocks}")

        # Print block assignments
        for block_num in range(NUM_BLOCKS):
            print(
                f"BLOCK {block_num}: {', '.join(str(wid) for wid in plan.blocks[block_num])}")

    print("\nJSON:")
    print(json.dumps(plan.tab()))
    sys.exit(0)


def parse_arguments():
    """Parse command line arguments.

    Returns:
        Parsed arguments object
    """
    parser = argparse.ArgumentParser(description="Workshop Plan Generator")

    # Required arguments
    parser.add_argument(
        "data_file", help="JSON file with workshop and user data")

    # Optional arguments
    parser.add_argument(
        "--plan", "-p", help="JSON string or file path of an existing plan to evaluate")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")
    parser.add_argument("--time-limit", "-t", type=int, default=DEFAULT_TIME_LIMIT_SECONDS,
                        help=f"Time limit for optimization in seconds (default: {DEFAULT_TIME_LIMIT_SECONDS})")
    parser.add_argument("--initial-plans", "-i", type=int, default=DEFAULT_NUM_INITIAL_PLANS,
                        help=f"Number of initial random plans to generate (default: {DEFAULT_NUM_INITIAL_PLANS})")
    parser.add_argument("--top-plans", "-n", type=int, default=DEFAULT_TOP_PLANS,
                        help=f"Number of top plans to display (default: {DEFAULT_TOP_PLANS})")

    return parser.parse_args()


def main():
    """Main entry point for the script."""
    # Parse command line arguments
    args = parse_arguments()

    # Make workshops and users available globally for Plan class methods
    global workshops, users, wid_list

    # Set global verbose flag
    global verbose
    verbose = args.verbose

    # Load data file
    data = load_data(args.data_file)

    # Initialize data structures
    workshops = {ws['wid']: ws for ws in data['workshops']}
    global workshops_per_block
    # Average workshops per block
    workshops_per_block = len(workshops) / NUM_BLOCKS
    
    # Get blocks_for_lecturers data if available
    blocks_for_lecturers = data.get('blocks_for_lecturers', None)
    if blocks_for_lecturers and verbose:
        print(f"Found blocks_for_lecturers data for {len(blocks_for_lecturers)} lecturers")

    users = initialize_users(data['users'], blocks_for_lecturers)
    wid_list = list(workshops.keys())
    
    # Process participation and get lecturer information
    lecturer_names = process_participation(data['participation'], users, wid_list)
    
    # Validate that all names in blocks_for_lecturers correspond to actual lecturers
    if blocks_for_lecturers:
        for lecturer in blocks_for_lecturers:
            lecturer_name = lecturer['name']
            if lecturer_name not in lecturer_names:
                raise ValueError(f"Error: '{lecturer_name}' in blocks_for_lecturers is not a lecturer (doesn't teach any workshop)")
                
        if verbose:
            print("All lecturer names in blocks_for_lecturers validated successfully")

    # Evaluate existing plan if provided
    if args.plan:
        evaluate_existing_plan(args.plan)

    # Generate and optimize plans
    plans_and_scores = optimize_plan(args.time_limit, args.initial_plans)

    # Display results
    display_results(plans_and_scores, args.top_plans)


if __name__ == "__main__":
    main()
