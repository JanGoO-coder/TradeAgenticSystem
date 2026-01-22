"use client"

import * as React from "react"
import { GripVerticalIcon } from "lucide-react"
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels"

import { cn } from "@/lib/utils"

function ResizablePanelGroup({
  className,
  ...props
}: React.ComponentProps<typeof PanelGroup>) {
  return (
    <PanelGroup
      data-slot="resizable-panel-group"
      className={cn(
        "flex h-full w-full data-[panel-group-direction=vertical]:flex-col",
        className
      )}
      {...props}
    />
  )
}

function ResizablePanel({
  ...props
}: React.ComponentProps<typeof Panel>) {
  return <Panel data-slot="resizable-panel" {...props} />
}

function ResizableHandle({
  withHandle,
  className,
  ...props
}: React.ComponentProps<typeof PanelResizeHandle> & {
  withHandle?: boolean
}) {
  return (
    <PanelResizeHandle
      data-slot="resizable-handle"
      className={cn(
        "bg-slate-700 hover:bg-emerald-500 active:bg-emerald-600 relative flex w-1.5 items-center justify-center transition-colors cursor-col-resize",
        className
      )}
      {...props}
    >
      {withHandle && (
        <div className="z-10 flex h-8 w-4 items-center justify-center rounded-sm bg-slate-600 border border-slate-500 hover:bg-emerald-600 hover:border-emerald-500">
          <GripVerticalIcon className="h-3 w-3 text-slate-300" />
        </div>
      )}
    </PanelResizeHandle>
  )
}

export { ResizablePanelGroup, ResizablePanel, ResizableHandle }
