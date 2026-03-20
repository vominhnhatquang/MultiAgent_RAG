// types/admin.ts

export interface SystemStats {
  documents: {
    total: number;
    indexed: number;
    processing: number;
    error: number;
  };
  chunks: {
    total: number;
  };
  sessions: {
    total: number;
    hot: number;
    warm: number;
    cold: number;
  };
  feedback: {
    thumbs_up: number;
    thumbs_down: number;
    satisfaction_rate: number;
  };
  models: {
    loaded: string[];
    available: string[];
  };
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  services?: {
    postgres: { status: string; latency_ms: number };
    qdrant: { status: string; latency_ms: number; vectors_count: number };
    redis: { status: string; used_memory_mb: number };
    ollama: { status: string; models_loaded: string[] };
  };
  memory?: {
    total_gb: number;
    used_gb: number;
    available_gb: number;
  };
}

export interface MemoryStats {
  total_gb: number;
  used_gb: number;
  services: {
    ollama: { used_mb: number; limit_mb: number };
    postgres: { used_mb: number; limit_mb: number };
    qdrant: { used_mb: number; limit_mb: number };
    redis: { used_mb: number; limit_mb: number };
    backend: { used_mb: number; limit_mb: number };
    frontend: { used_mb: number; limit_mb: number };
  };
}
