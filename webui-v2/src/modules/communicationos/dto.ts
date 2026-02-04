/**
 * CommunicationOS Module DTOs
 * Covers: Voice sessions, channels, messaging
 * Note: Placeholder for future implementation
 */

// TODO: Add CommunicationOS DTOs when backend APIs are finalized
export interface VoiceSession {
  id: string
  user_id: string
  status: string
  started_at: string
  ended_at?: string
}

export interface Channel {
  id: string
  name: string
  type: string
  created_at: string
}

export interface Message {
  id: string
  channel_id: string
  sender_id: string
  content: string
  created_at: string
}

// ========== API Request/Response Types ==========

export interface ListChannelsRequest {
  type?: string
}

export type ListChannelsResponse = Channel[]

export interface CreateChannelRequest {
  name: string
  type: string
}

export type CreateChannelResponse = Channel

export interface ListSessionsRequest {
  status?: string
}

export interface Session {
  id: string
  user_id: string
  status: string
  created_at: string
}

export type ListSessionsResponse = Session[]

export interface ListVoiceSessionsRequest {
  status?: string
}

export type ListVoiceSessionsResponse = VoiceSession[]

export interface ListMCPServersRequest {
  status?: string
}

export interface MCPServer {
  id: string
  name: string
  status: string
  endpoint: string
  created_at: string
}

export type ListMCPServersResponse = MCPServer[]
