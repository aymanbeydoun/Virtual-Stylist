import { api } from "@/api/client";
import type { Outfit } from "@/api/types";

export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface RefineResponse {
  outfit: Outfit;
  message: Message;
}

export const refineApi = {
  async getOutfit(outfitId: string) {
    return api<Outfit>(`/stylist/outfits/${outfitId}`);
  },

  async getConversation(outfitId: string) {
    return api<{ messages: Message[] }>(`/stylist/outfits/${outfitId}/conversation`);
  },

  async send(outfitId: string, message: string) {
    return api<RefineResponse>(`/stylist/outfits/${outfitId}/refine`, {
      method: "POST",
      json: { message },
    });
  },

  async recompose(outfitId: string) {
    return api<Outfit>(`/stylist/outfits/${outfitId}/recompose`, {
      method: "POST",
    });
  },
};
