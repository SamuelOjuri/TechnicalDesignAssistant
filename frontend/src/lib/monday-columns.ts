// Monday.com board configuration details for item creation via API

// Monday.com column mapping
export const MONDAY_COLUMN_MAPPING = {
  'Date Received': 'Date Received',
  'Hour Received': 'Hour Received', 
  'Post Code': 'Zip Code',
  'Drawing Reference': 'TP Ref',
  'New Enq / Amend': 'New Enq / Amend'
} as const;

export const MONDAY_BOARD_CONFIG = {
  boardId: 1882196103, // was 1977397150
  groupId: 'group_mkpbd6vy', // was 'group_mkrbr4jr'
  emailColumnId: 'file_mkpbm883'  
} as const;

// Column IDs for reference
export const MONDAY_COLUMN_IDS = {
  name: 'name',
  email: 'file_mkpbm883',
  priority: 'color_mkpb34xe',
  designer: 'person',
  status: 'status',
  timeTracking: 'duration_mkq2r9rh',
  dateReceived: 'date_mkpb23av',
  hourReceived: 'hour_mkpbb3j1',
  newEnqAmend: 'dropdown_mkpb98es',
  tpRef: 'board_relation_mkpbm5np',
  projectName: 'lookup_mkpb44am',
  zipCode: 'dropdown_mkpbafca',
  dateCompleted: 'date_mkqx70pe',
  hourCompleted: 'hour_mkqxbfgv'
} as const;