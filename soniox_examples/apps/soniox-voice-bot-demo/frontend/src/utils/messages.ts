import z from "zod";

const transcriptionMessageSchema = z.object({
  type: z.literal("transcription"),
  final_text: z.string(),
  non_final_text: z.string(),
});

const llmResponseMessageSchema = z.object({
  type: z.literal("llm_response"),
  text: z.string(),
});

const sessionStartMessageSchema = z.object({
  type: z.literal("session_start"),
});

const userSpeechStartMessageSchema = z.object({
  type: z.literal("user_speech_start"),
});

const userSpeechEndMessageSchema = z.object({
  type: z.literal("user_speech_end"),
});

export const messageSchema = z.union([
  transcriptionMessageSchema,
  llmResponseMessageSchema,
  sessionStartMessageSchema,
  userSpeechStartMessageSchema,
  userSpeechEndMessageSchema,
]);

export type Message = z.infer<typeof messageSchema>;

// Order confirmation — sent by server after place_order succeeds
export const orderItemSchema = z.object({
  name: z.string(),
  quantity: z.number(),
  price: z.number(),
  notes: z.string().optional().default(""),
});

export type OrderItem = z.infer<typeof orderItemSchema>;

export const orderConfirmedSchema = z.object({
  type: z.literal("order_confirmed"),
  order_id: z.string(),
  customer_name: z.string(),
  phone_number: z.string(),
  order_type: z.string(),
  items: z.array(orderItemSchema),
  total_amount: z.number(),
  wait_time: z.string(),
  special_instructions: z.string().optional().default(""),
});

export type OrderConfirmed = z.infer<typeof orderConfirmedSchema>;

export function updateMessages(
  messages: Message[],
  message: Message
): Message[] {
  const previousMessages = messages.slice(0, -1);
  const lastMessage = messages.at(-1);

  if (!lastMessage) {
    return [message];
  }

  if (lastMessage.type !== message.type) {
    return [...previousMessages, lastMessage, message];
  }

  if (
    lastMessage.type === "transcription" &&
    message.type === "transcription"
  ) {
    return [
      ...previousMessages,
      {
        type: "transcription",
        final_text: lastMessage.final_text + message.final_text,
        non_final_text: message.non_final_text,
      },
    ];
  } else if (
    lastMessage.type === "llm_response" &&
    message.type === "llm_response"
  ) {
    return [
      ...previousMessages,
      {
        type: "llm_response",
        text: lastMessage.text + message.text,
      },
    ];
  }

  console.error("Unexpected message type");
  return messages;
}
