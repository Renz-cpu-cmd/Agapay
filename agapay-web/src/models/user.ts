export type UserRole = 'Admin' | 'Officer' | 'Responder' | 'Resident';
export type UserStatus = 'Active' | 'Inactive';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  barangay: string;
  phone: string;
  status: UserStatus;
  createdAt: string;
  lastLogin?: string;
  badgeNumber?: string;
}
