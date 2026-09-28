export type UserRole = 'SUPER_ADMIN' | 'HR_ADMIN' | 'DEPT_MANAGER' | 'EMPLOYEE'

export interface User {
  id: number
  email: string
  username: string
  full_name: string
  role: UserRole
  is_active: boolean
  employee_id?: number
  last_login?: string
}

export interface Employee {
  id: number
  employee_id: string
  biometric_code?: string
  first_name: string
  last_name?: string
  full_name: string
  email?: string
  phone?: string
  gender?: string
  date_of_birth?: string
  joining_date?: string
  employment_type?: string
  department_id?: number
  department_name?: string
  designation_id?: number
  designation_name?: string
  shift_id?: number
  shift_code?: string
  basic_salary?: number
  security_fund_deduction?: number
  accumulated_security_fund?: number
  bank_name?: string
  account_number?: string
  bank_account_number?: string
  ifsc_code?: string
  bank_ifsc?: string
  pan_number?: string
  pf_number?: string
  esi_number?: string
  is_active: boolean
}

export interface Department {
  id: number
  name: string
  code: string
  description?: string
  manager_id?: number
  is_active: boolean
}

export interface Shift {
  id: number
  name: string
  code: string
  start_time: string
  end_time: string
  is_overnight: boolean
  is_split?: boolean
  start_time_2?: string
  end_time_2?: string
  is_overnight_2?: boolean
  grace_period_minutes: number
  expected_working_minutes: number
  ot_threshold_minutes: number
  is_active: boolean
}

export type AttendanceStatus =
  | 'PRESENT'
  | 'ABSENT'
  | 'PRESENT_INCOMPLETE'
  | 'PRESENT_OVERNIGHT'
  | 'LEAVE'
  | 'HOLIDAY'
  | 'WEEKLY_OFF'

export interface AttendanceRecord {
  id: number
  employee_id: number
  employee_name?: string
  employee_code?: string
  biometric_code?: string
  department_id?: number
  department?: string
  department_name?: string
  shift_code?: string
  attendance_date: string
  in_time?: string
  out_time?: string
  source_in_time?: string
  source_out_time?: string
  work_minutes?: number
  ot_minutes?: number
  status: AttendanceStatus
  is_late: boolean
  is_corrected: boolean
  corrected_in_time?: string
  corrected_out_time?: string
  correction_reason?: string
}

export interface AttendanceImport {
  id: number
  filename: string
  file_hash: string
  date_range_start?: string
  date_range_end?: string
  total_records: number
  records_imported: number
  records_failed: number
  records_skipped: number
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'PARTIAL'
  created_at: string
}

export interface LeaveType {
  id: number
  name: string
  code: string
  is_paid: boolean
  max_days_per_year?: number
  description?: string
}

export interface LeaveRequest {
  id: number
  employee_id: number
  employee_name?: string
  employee_code?: string
  leave_type: string
  leave_code?: string
  start_date: string
  end_date: string
  days_count: number
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED'
  reason?: string
  applied_at: string
  review_comment?: string
}

export interface PayrollRecord {
  id: number
  employee_id: number
  employee_name?: string
  employee_code?: string
  biometric_code?: string
  department?: string
  department_name?: string
  total_working_days: number
  present_days: number
  absent_days: number
  leave_days: number
  paid_leave_days: number
  loss_of_pay_days: number
  ot_hours: number
  basic_salary: number
  ot_amount: number
  gross_salary: number
  total_deductions: number
  deductions?: number
  net_salary: number
  total_salary?: number
  status: 'DRAFT' | 'NO_DATA' | 'UNDER_REVIEW' | 'FINALIZED' | 'PAID'
}

export interface DashboardStats {
  total_employees: number
  present_today: number
  absent_today: number
  incomplete_today: number
  late_today: number
  on_leave_today: number
  ot_hours_today: number
  monthly_payroll: number
  as_of: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages?: number
}
