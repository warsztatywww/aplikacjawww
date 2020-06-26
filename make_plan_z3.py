#!/usr/bin/python3
import json
import sys
import time
import z3

TYPE_PARTICIPANT = "Participant"
TYPE_LECTURER = "Lecturer"
PARTICIPANT_MUL = 2


def flatten(l):
    flat = []
    for ll in l:
        flat += list(ll)
    return flat


class Context:
    def __init__(self, block_num, slot_num, users, workshops):
        self.blocks = [[z3.Int(f"slot_{i}_{j}") for j in range(slot_num)]
                  for i in range(block_num)]
        self.slots = flatten(self.blocks)
        self.users = users
        self.workshops = workshops

    def solve(self):
        self.s = z3.Optimize()
        points = 0
        self.s.add(z3.Distinct(self.slots))
        self.s.add([z3.And(0 <= slot, slot < len(self.slots)) for slot in self.slots])

        for _, user in self.users.items():
            user.one_workshop_in_block(self)
        for _, workshop in self.workshops.items():
            workshop.not_in_disallowed_block(self)
        for _, user in self.users.items():
            points += user.get_points(self)

        self.s.maximize(points)
        print("PREPARATION READY!")
        print("CHECK: ", self.s.check())
        print("MODEL: ", self.s.model())


class User:
    def __init__(self, info, idx):
        self.name = info['name']
        self.id = info['uid']
        self.type = info['type']
        self.idx = idx
        self.participations = []
        self.workshops = []

    def one_workshop_in_block(self, ctx):
        ctx.s.add([
            z3.Not(z3.And(
                z3.Or([block[s1] == z3.IntVal(workshop.idx) for workshop in self.workshops]),
                z3.Or([block[s2] == z3.IntVal(workshop.idx) for workshop in self.workshops]),
            ))
            for block in ctx.blocks
            for s1 in range(len(block))
            for s2 in range(len(block)) if s2 != s1
        ])

    def get_points(self, ctx):
        empty_blocks = 0
        for block in ctx.blocks:
            empty_blocks = z3.If(z3.Or(
                [slot == participation.idx for slot in block for participation in self.participations]
            ), empty_blocks+1, empty_blocks)
        if self.type == TYPE_PARTICIPANT:
            return -empty_blocks * empty_blocks * PARTICIPANT_MUL
        else:
            return -empty_blocks * empty_blocks


class Workshop:
    def __init__(self, info, idx, users):
        self.idx = idx
        self.name = info['name']
        self.id = info['wid']
        self.lecturers = []
        for lecturer in info['lecturers']:
            self.lecturers.append(users[lecturer])
            users[lecturer].workshops.append(self)
        self.participants = []
        self.forbidden_blocks = []
        if 'forbidden_blocks' in info:
            self.forbidden_blocks = info['forbidden_blocks']

    def not_in_disallowed_block(self, ctx):
        ctx.s.add([
            slot != self.idx
            for block in self.forbidden_blocks
            for slot in ctx.blocks[block]
        ])


def add_participation(workshop, user):
    workshop.participants.append(user)
    user.participations.append(workshop)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage {file} data.json".format(file=sys.argv[0]))
        sys.exit(1)

    # Reads data in format of dataForPlan.
    with open(sys.argv[1]) as f:
        data = json.load(f)

    users = {u['uid']: User(u, idx) for idx, u in enumerate(data['users'])}
    workshops = {ws['wid']: Workshop(ws, idx, users) for idx, ws in enumerate(data['workshops'])}
    for participation in data['participation']:
        add_participation(workshops[participation['wid']], users[participation['uid']])

    ctx = Context(block_num=8,
                  slot_num=4,
                  users=users,
                  workshops=workshops)
    ctx.solve()
