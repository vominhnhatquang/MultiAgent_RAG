"use client";

import Link from "next/link";
import { useAdmin } from "@/hooks/useAdmin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  ArrowLeft, 
  RefreshCw, 
  FileText, 
  Layers, 
  MessageSquare, 
  ThumbsUp,
  MemoryStick,
  Server,
  AlertCircle,
  CheckCircle2,
  Database
} from "lucide-react";

export default function AdminPage() {
  const { stats, health, memory, isLoading, error, refreshAll } = useAdmin();

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const formatMB = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <Link href="/chat">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-5 w-5" />
              </Button>
            </Link>
            <h1 className="text-lg font-semibold">Admin Dashboard</h1>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={refreshAll}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-6xl p-4 space-y-6">
        {/* Error */}
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {/* Documents */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Documents</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading || !stats ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats.documents.total}</div>
                  <p className="text-xs text-muted-foreground">
                    {stats.documents.indexed} indexed, {stats.documents.processing} processing
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* Chunks */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Chunks</CardTitle>
              <Layers className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading || !stats ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats.chunks.total}</div>
                  <p className="text-xs text-muted-foreground">
                    Total indexed chunks
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* Sessions */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Sessions</CardTitle>
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading || !stats ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <>
                  <div className="text-2xl font-bold">{stats.sessions.total}</div>
                  <p className="text-xs text-muted-foreground">
                    {stats.sessions.hot} hot, {stats.sessions.warm} warm, {stats.sessions.cold} cold
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* Feedback */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Feedback</CardTitle>
              <ThumbsUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {isLoading || !stats ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <>
                  <div className="text-2xl font-bold">
                    {Math.round(stats.feedback.satisfaction_rate * 100)}%
                  </div>
                  <p className="text-xs text-muted-foreground">
                    👍 {stats.feedback.thumbs_up} 👎 {stats.feedback.thumbs_down}
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Memory Usage */}
        {memory && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
              <MemoryStick className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Total System</span>
                    <span className="text-muted-foreground">
                      {memory.used_gb.toFixed(1)} / {memory.total_gb.toFixed(1)} GB
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${(memory.used_gb / memory.total_gb) * 100}%` }}
                    />
                  </div>
                </div>

                {/* Service Breakdown */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 pt-4">
                  {Object.entries(memory.services).map(([service, data]) => {
                    const serviceData = data as { used_mb: number; limit_mb: number };
                    return (
                      <div key={service} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="capitalize">{service}</span>
                          <span className="text-muted-foreground">
                            {formatMB(serviceData.used_mb)} / {formatMB(serviceData.limit_mb)}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full rounded-full bg-secondary transition-all"
                            style={{ width: `${(serviceData.used_mb / serviceData.limit_mb) * 100}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Services Status */}
        {health?.services && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Services</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(health.services).map(([service, data]) => {
                  const serviceData = data as { status: string; latency_ms?: number };
                  return (
                    <div key={service} className="flex items-center gap-2">
                      {serviceData.status === "up" ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-red-500" />
                      )}
                      <div>
                        <p className="text-sm font-medium capitalize">{service}</p>
                        <p className="text-xs text-muted-foreground">
                          {serviceData.status === "up" ? "Healthy" : "Down"}
                          {"latency_ms" in serviceData && ` • ${serviceData.latency_ms}ms`}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Models */}
        {stats?.models && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Loaded Models</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {stats.models.loaded.map((model: string) => (
                  <span
                    key={model}
                    className="px-2 py-1 rounded-full bg-green-500/10 text-green-600 text-xs font-medium"
                  >
                    {model}
                  </span>
                ))}
                {stats.models.available.map((model: string) => (
                  <span
                    key={model}
                    className="px-2 py-1 rounded-full bg-muted text-muted-foreground text-xs"
                  >
                    {model} (available)
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Footer */}
        <div className="text-center text-xs text-muted-foreground pt-4">
          Data refreshes automatically every 30 seconds • Last updated: {new Date().toLocaleTimeString()}
        </div>
      </main>
    </div>
  );
}
