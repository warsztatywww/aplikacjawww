import functools

from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Dict, Optional
import json

def cached(method):
    attr = f"_cache_{method.__name__}"
    @functools.wraps(method)
    def wrapper(self, *args):
        cache = self.__dict__.setdefault(attr, {})
        if args not in cache:
            cache[args] = method(self, *args)
        return cache[args]
    return wrapper

@dataclass
class CampAttendance:
    arrival: date
    departure: date

BlockId = int
WorkshopId = int
UserId = int

@dataclass
class Workshop:
    workshop_id: WorkshopId
    name: str
    lecturers: List[UserId]
    participants: List[UserId]

    def all_participants(self):
        return set(self.lecturers + self.participants)

@dataclass
class Block:
    block_id: BlockId
    name: str
    start: date
    end: date

    def feasible_for_attendance(self, attendance: CampAttendance):
        return attendance.arrival <= self.start and self.end <= attendance.departure

Plan = Dict[BlockId, List[WorkshopId]]

def get_workshop_block(plan: Plan, workshop_id: WorkshopId) -> Optional[BlockId]:
    for block_id, workshop_ids in plan.items():
        if workshop_id in workshop_ids:
            return block_id
    return None

@dataclass
class User:
    LECTURER = "lecturer"
    PARTICIPANT = "participant"

    user_id: UserId
    name: str
    role: str # "lecturer" or "participant"
    attendance: CampAttendance

    def is_lecturer(self):
        return self.role == User.LECTURER
    
    def is_participant(self):
        return self.role == User.PARTICIPANT

@dataclass
class CampInfo:
    workshops: Dict[WorkshopId, Workshop]
    users: Dict[UserId, User]
    workshop_participants: Dict[WorkshopId, List[UserId]]


    def __init__(self, blocks: List[Block], workshops: Dict[WorkshopId, Workshop], users: Dict[UserId, User]):
        self.blocks = { block.block_id : block for block in blocks }
        self.workshops = {workshop.workshop_id : workshop for workshop in workshops}
        self.users = {user.user_id : user for user in users}
        self.user_names = {user_id: user.name for user_id, user in self.users.items()}

    @cached
    def workshop_ids(self):
        return list(self.workshops.keys())

    def user_enlisted_workshops(self, uid: UserId) -> List[WorkshopId]:
        '''
        List of workshops user enlisted in (wants to participate).
        '''
        return [
            wid for wid, workshop in self.workshops.items()
            if uid in workshop.participants
        ]

    def user_lectured_workshops(self, user_id: UserId) -> List[WorkshopId]:
        '''
        List of workshops user is lecturer of.
        '''
        return [
            wid for wid, workshop in self.workshops.items()
            if user_id in workshop.lecturers
        ]

    def workshop_participants(self, wid: WorkshopId):
        return self.workshops[wid].all_participants()
    
    def attendance(self, uid: UserId) -> CampAttendance:
        return self.users[uid].attendance

    def user_present_during_block(self, user_id: UserId, block_id: BlockId):
        attendance = self.users[user_id].attendance
        return self.blocks[block_id].feasible_for_attendance(attendance)
    
    @cached
    def user_attendable_blocks(self, user_id: UserId) -> List[BlockId]:
        return [block_id for block_id in self.blocks.keys() if self.user_present_during_block(user_id, block_id)]

    @cached
    def blocks_feasible_for_workshop(self, workshop_id: WorkshopId) -> List[BlockId]:
        workshop = self.workshops[workshop_id]
        return [
            block_id for block_id, block in self.blocks.items()
            if all(block.feasible_for_attendance(self.attendance(lecturer_id))
                for lecturer_id in workshop.lecturers)
        ] 

    
@dataclass
class Blocks:
    blocks: Dict[BlockId, Block]
    feasible_for_workshop: Dict[WorkshopId, List[BlockId]]

    def from_blocks_and_camp_info(blocks: List[BlockId, Block], camp_info: CampInfo) -> 'Blocks':
        blocks = { block.block_id : block for block in blocks }
        feasible_for_workshop = {}
        for wid, workshop in camp_info.workshops.items():
            feasible_blocks = []
            for block_id, block in blocks.items():
                if all(block.feasible_for_attendance(camp_info.attendance(lecturer_id)) for lecturer_id in workshop.lecturers):
                    feasible_blocks.append(block_id)
            feasible_for_workshop[wid] = feasible_blocks
        return Blocks(blocks=blocks, feasible_for_workshop=feasible_for_workshop)



def load_camp_info(path: str, blocks: List[Block]) -> CampInfo:
    with open(path, 'r') as f:
        data = json.load(f)
    
    workshops = [
        Workshop(
            workshop_id=w['wid'],
            name=w['name'],
            lecturers=w['lecturers'],
            participants=[
                p['uid'] for p in data['participation'] if p['wid'] == w['wid']
            ]
        )
        for w in data['workshops']
    ]

    users = [
            User(
            user_id=user['uid'],
            name=user['name'],
            role=user['type'],
            attendance=CampAttendance(
                arrival=datetime.strptime(user['start'], '%Y-%m-%d').date(),
                departure=datetime.strptime(user['end'], '%Y-%m-%d').date()
            )
        )
        for user in data["users"]
    ]

    return CampInfo(blocks, workshops, users)