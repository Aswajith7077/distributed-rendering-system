"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Grid3X3, Activity, BarChart2, Home } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { name: "Renderer", href: "/", icon: Home },
  { name: "Health", href: "/health", icon: Activity },
  { name: "Benchmarks", href: "/benchmark", icon: BarChart2 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col h-screen sticky top-0">
      <div className="p-6 flex items-center gap-3 border-b border-zinc-800">
        <Grid3X3 className="w-6 h-6 text-zinc-100" />
        <h1 className="text-base font-semibold tracking-tight text-zinc-100">
          Tile Renderer
        </h1>
      </div>
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer",
                isActive
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50"
              )}
            >
              <Icon className="w-5 h-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-zinc-800">
        <div className="text-[10px] text-zinc-500 text-center">
          PDC Distributed System v1.0
        </div>
      </div>
    </div>
  );
}
