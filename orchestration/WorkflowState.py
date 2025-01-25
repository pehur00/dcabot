from enum import Enum

class WorkflowState(Enum):
    INITIAL = "initial"
    CHECK_ENTRY = "check_entry"
    OPEN_POSITION = "open_position"
    MONITOR_POSITION = "monitor_position"
    CLOSE_POSITION = "close_position"