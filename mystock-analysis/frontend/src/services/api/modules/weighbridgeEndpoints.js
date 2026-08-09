export const WEIGHBRIDGE_ENDPOINTS = {
  ENTRY: {
    CONFIRM: '/api/in/confirm'
  },
  EXIT: {
    CONFIRM: '/api/out/confirm'
  },
  PRINT: '/api/print',
  TICKET: {
    BY_NO: (ticketNo) => `/api/ticket/${ticketNo}`,
    TODAY: '/api/tickets/today'
  },
  DB: {
    STATUS: '/api/db/status'
  },
  PO: {
    BY_NO: (poNo) => `/api/po/${poNo}`
  }
}
