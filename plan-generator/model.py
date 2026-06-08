from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Dict, Optional
import json

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
    LECTURER = "Lecturer"
    PARTICIPANT = "Participant"

    user_id: UserId
    name: str
    role: str # "lecturer" or "participant"

    def is_lecturer(self):
        return self.role == User.LECTURER
    
    def is_participant(self):
        return self.role == User.PARTICIPANT

@dataclass
class CampInfo:
    workshops: Dict[WorkshopId, Workshop]
    attendance: Dict[UserId, CampAttendance]
    users: Dict[UserId, User]
    workshop_participants: Dict[WorkshopId, List[UserId]] # not lecturers


    def __init__(self, workshops: Dict[WorkshopId, Workshop], attendance: Dict[UserId, CampAttendance], users: Dict[UserId, User]):
        self.workshops = workshops
        self.attendance = attendance
        self.users = users
        self.user_names = {user_id: user.name for user_id, user in users.items()}

    def user_workshops(self, uid: UserId) -> List[WorkshopId]:
        return [
            wid for wid, workshop in self.workshops.items()
            if uid in workshop.all_participants()
        ]

    def workshop_participants(self, wid: WorkshopId):
        return self.workshops[wid].all_participants()
    
@dataclass
class Blocks:
    blocks: Dict[BlockId, Block]
    feasible_for_workshop: Dict[WorkshopId, List[BlockId]]

    def from_blocks_and_camp_info(blocks: Dict[BlockId, Block], camp_info: CampInfo) -> 'Blocks':
        feasible_for_workshop = {}
        for wid, workshop in camp_info.workshops.items():
            feasible_blocks = []
            for block_id, block in blocks.items():
                if all(block.feasible_for_attendance(camp_info.attendance[lecturer_id]) for lecturer_id in workshop.lecturers):
                    feasible_blocks.append(block_id)
            feasible_for_workshop[wid] = feasible_blocks
        return Blocks(blocks=blocks, feasible_for_workshop=feasible_for_workshop)



def load_camp_info(path: str) -> CampInfo:
    with open(path, 'r') as f:
        data = json.load(f)
    
    workshops = {}

    for w in data['workshops']:
        workshops[w['wid']] = Workshop(
            workshop_id=w['wid'],
            name=w['name'],
            lecturers=w['lecturers'],
            participants=[]
        )

    attendance = {}
    users = {}

    for user in data["users"]:
        attendance[user['uid']] = CampAttendance(
            arrival=datetime.strptime(user['start'], '%Y-%m-%d').date(),
            departure=datetime.strptime(user['end'], '%Y-%m-%d').date()
        )
        users[user['uid']] = User(
            user_id=user['uid'],
            name=user['name'],
            role=user['type']
        )

    for p in data['participation']:
        if p['wid'] in workshops:
            workshops[p['wid']].participants.append(p['uid'])

    return CampInfo(workshops=workshops, attendance=attendance, users=users)