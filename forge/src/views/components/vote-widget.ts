import { html } from "hono/html";

export function voteWidget(
  pluginName: string,
  score: number,
  userVote: number,
  showDownvote: boolean
) {
  const upActive = userVote === 1;
  const downActive = userVote === -1;
  const upValue = upActive ? 0 : 1;
  const downValue = downActive ? 0 : -1;

  return html`
    <div id="vote-${pluginName}" class="flex items-center gap-1">
      <button
        hx-post="/plugins/${pluginName}/vote"
        hx-vals='{"value":${upValue}}'
        hx-target="#vote-${pluginName}"
        hx-swap="outerHTML"
        name="detail-vote"
        class="p-1 rounded hover:bg-gray-100 ${upActive ? "text-orange-500" : "text-gray-400"}"
        title="Upvote"
      >
        &#9650;
      </button>
      <span class="text-sm font-medium min-w-[2ch] text-center">${score}</span>
      ${showDownvote
        ? html`
            <button
              hx-post="/plugins/${pluginName}/vote"
              hx-vals='{"value":${downValue}}'
              hx-target="#vote-${pluginName}"
              hx-swap="outerHTML"
              name="detail-vote"
              class="p-1 rounded hover:bg-gray-100 ${downActive ? "text-blue-500" : "text-gray-400"}"
              title="Downvote"
            >
              &#9660;
            </button>
          `
        : ""}
    </div>
  `;
}
