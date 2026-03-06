CREATE TABLE "context_summaries" (
	"id" varchar PRIMARY KEY NOT NULL,
	"conversation_id" varchar,
	"summary" text,
	"messages_summarized" varchar,
	"created_at" timestamp
);
--> statement-breakpoint
CREATE TABLE "tools" (
	"id" varchar PRIMARY KEY NOT NULL,
	"name" varchar NOT NULL,
	"description" text NOT NULL,
	"tool_type" varchar NOT NULL,
	"content" text NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "tools_name_unique" UNIQUE("name")
);
--> statement-breakpoint
ALTER TABLE "context_summaries" ADD CONSTRAINT "context_summaries_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations"("id") ON DELETE no action ON UPDATE no action;