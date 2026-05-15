import { create } from "zustand";

interface AuthState {
  devUserId: string | null;
  signIn: (id: string) => void;
  signOut: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  devUserId: null,
  signIn: (id) => set({ devUserId: id }),
  signOut: () => set({ devUserId: null }),
}));
