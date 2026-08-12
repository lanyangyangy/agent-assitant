import { Wrench } from "lucide-react";

import type { ToolSchema } from "../api/types";

interface ToolCatalogProps {
  tools: ToolSchema[];
}

export function ToolCatalog({ tools }: ToolCatalogProps) {
  return (
    <section className="tool-catalog">
      <div className="tool-catalog-title">
        <Wrench size={16} />
        <h2>工具目录</h2>
      </div>

      {tools.length === 0 ? (
        <div className="empty-state compact">暂无工具</div>
      ) : (
        tools.map((tool) => (
          <article key={tool.name} className="tool-card">
            <h3>{tool.name}</h3>
            <p>{tool.description}</p>
            <dl>
              {tool.parameters.map((parameter) => (
                <div key={parameter.name}>
                  <dt>{parameter.name}</dt>
                  <dd>
                    {parameter.type}
                    {parameter.required ? "，必填" : "，可选"}
                  </dd>
                </div>
              ))}
            </dl>
          </article>
        ))
      )}
    </section>
  );
}
