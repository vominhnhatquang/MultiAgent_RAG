import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar Skeleton */}
      <aside className="hidden md:flex w-72 flex-col border-r bg-muted/50">
        {/* Header */}
        <div className="h-14 border-b px-4 flex items-center">
          <Skeleton className="h-6 w-32" />
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <Skeleton className="h-10 w-full" />
        </div>

        {/* Mode Toggle */}
        <div className="px-4 pb-2">
          <Skeleton className="h-16 w-full" />
        </div>

        {/* Navigation */}
        <div className="px-4 pb-2 space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>

        {/* Sessions List */}
        <div className="flex-1 px-4 py-2 space-y-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-4 w-24 mt-4" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>

        {/* Footer */}
        <div className="border-t p-4">
          <Skeleton className="h-4 w-full" />
        </div>
      </aside>

      {/* Chat Area Skeleton */}
      <main className="flex-1 flex flex-col">
        {/* Messages Area */}
        <div className="flex-1 p-4 space-y-6 max-w-3xl mx-auto w-full">
          {/* Welcome Message Skeleton */}
          <div className="flex h-[50vh] flex-col items-center justify-center text-center space-y-4">
            <Skeleton className="h-12 w-12 rounded-full" />
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t bg-background p-4">
          <div className="max-w-3xl mx-auto flex gap-2">
            <Skeleton className="h-14 flex-1" />
            <Skeleton className="h-14 w-14" />
          </div>
        </div>
      </main>
    </div>
  );
}
