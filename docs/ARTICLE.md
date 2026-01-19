# AI in Motion: Why I'm Now Bullish on Enterprise Agentic AI

Like many technologists, I approach AI trends with healthy skepticism. Earlier this year, the term "Agentic AI" seemed to be everywhere — yet poorly defined and wildly ambitious. The use cases felt unreal, the workflows impractical. My core objection was simple but fundamental: **enterprises will never tolerate non-deterministic actions that can impact their internal systems.**

I wanted to challenge this position, so I decided to try and build something that would *prove me right*. I set out to create an LLM-driven workflow that, in my mind, would be a non-starter for any serious enterprise: a system where a model could influence real internal operations.

I put that to the test in the most practical way I could: I built a real enterprise web application, then retrofitted it to work with a Large Language Model through the Model Context Protocol (MCP).

The results, quite frankly, surprised me. By putting clear boundaries around what the model could do, I ended up with something that felt enterprise-acceptable, and that forced me to rethink my position. However, the experiment went even further: It allowed me to leverage new functionality that made the base application far better than its original design. This article elaborates on my experiences.

### What I Built

The experiment was straightforward: build a corporate vacation management system. Employees track their vacation days, request time off, check balances — all the mundane but critical HR functions that exist in every organization. I implemented it first as a traditional REST API with a web frontend. Nothing fancy, just standard enterprise plumbing.

Then came the interesting part: I added an MCP server interface to the same backend. This allowed me to expose the vacation management capabilities as "tools" that an LLM could invoke. Finally, I built a simple chatbot frontend that let users manage their vacation time through natural conversation instead of clicking through forms and menus.

### The Surprising Results

The results weren't just good; they were revelatory. The system worked far better than I anticipated, and more importantly, it **enabled genuinely new behaviors** that wouldn't exist in a traditional interface.

Instead of navigating through multiple screens to check your balance, see upcoming vacation days, and calculate whether you have enough time for a two-week trip, users could simply ask: *"Do I have enough vacation days to take off December 20th through January 3rd?"* The AI would check their balance, calculate business days (excluding weekends and holidays), confirm availability, and even offer to create the request—all in a natural conversation.

What struck me most was the composability. The chatbot didn't just replicate existing UI workflows; it **combined multiple operations intelligently**. It understood context, anticipated follow-up questions, and presented information in exactly the format users needed at that moment. This wasn't about replacing buttons with words — it was about fundamentally rethinking the interaction model.

### Why This Changes My Position

I'm not prone to hyperbole, but this experiment forced me to seriously reconsider my position on AI in the enterprise. Yes, there are legitimate concerns about non-determinism, hallucinations, and unintended actions. But I now see a viable path forward.

The key insight is this: **MCP allows enterprises to expose carefully controlled, well-defined capabilities to AI systems while maintaining complete authority over what actually happens.** The AI doesn't get direct database access or the ability to execute arbitrary code. Instead, it calls specific, authorized functions that implement business logic, enforce permissions, and maintain audit trails—just like any other API consumer.

The difference is that the AI can orchestrate these functions in response to natural language, understand context across multiple interactions, and adapt to the user's actual needs rather than forcing them into predefined workflows.

### The Bigger Picture

What I'm starting to envision is a new paradigm where critical business functions become composable building blocks. Imagine connecting vacation management with project scheduling, team availability, and workload planning. An employee could ask, *"When's the best time for me to take a week off given my project deadlines and team coverage?"* and receive an intelligent answer that considers multiple systems and constraints.

### My Revised Position

I'm revising my stance: I'm now cautiously optimistic — even bullish — on Enterprise Agentic AI. The hazards are real, but they're manageable. The potential is enormous. And most importantly, the technology is ready now, not five years from now.

The path forward requires thoughtful implementation: careful API design, robust authentication and authorization, comprehensive audit logging, and clear boundaries around what AI can and cannot do. But having built a working system over a long weekend, I can confidently say the technical barriers are lower than I expected.

**Consider me "on board" with Enterprise Agentic AI.**

The question is no longer whether this will transform how we interact with enterprise systems, but how quickly organizations will adopt it—and who will gain the competitive advantage by moving first.

### Additional Details

For a more thorough walkthrough of the work I did, please see [this document](./WALKTHROUGH.md).