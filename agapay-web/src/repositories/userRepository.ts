import { User, UserRole } from '@/models/user';
import { initialUsers } from '@/services/mockData';

export interface UserRepository {
  getUsers(): Promise<User[]>;
  createUser(params: { name: string; email: string; role: UserRole; barangay: string; phone: string }): Promise<User>;
  updateUserStatus(id: string, status: 'Active' | 'Inactive'): Promise<User>;
}

export class MockUserRepository implements UserRepository {
  private users: User[] = [...initialUsers];

  async getUsers(): Promise<User[]> {
    return [...this.users];
  }

  async createUser(params: {
    name: string;
    email: string;
    role: UserRole;
    barangay: string;
    phone: string;
  }): Promise<User> {
    const newUser: User = {
      id: `USR-${Date.now().toString().slice(-4)}`,
      name: params.name,
      email: params.email,
      role: params.role,
      barangay: params.barangay,
      phone: params.phone,
      status: 'Active',
      createdAt: new Date().toISOString().split('T')[0],
      badgeNumber: `LGU-DRRM-${Math.floor(100 + Math.random() * 900)}`,
    };
    this.users.push(newUser);
    return newUser;
  }

  async updateUserStatus(id: string, status: 'Active' | 'Inactive'): Promise<User> {
    const idx = this.users.findIndex((u) => u.id === id);
    if (idx === -1) throw new Error('User not found');

    const updated = { ...this.users[idx], status };
    this.users[idx] = updated;
    return updated;
  }
}

export const userRepository = new MockUserRepository();
