import { render, screen } from "@testing-library/react";
import { MutationTable } from "../components/MutationTable";
import { getMockSessionDetail } from "../lib/mock-data";

it("displays the currency of each invoice version", () => {
  const session = getMockSessionDetail("b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21");
  if (!session || !session.mutations.updated[0]) throw new Error("missing fixture");
  const mutation = { ...session.mutations.updated[0] };
  if (!mutation.before || !mutation.after) throw new Error("missing invoice");
  mutation.before = { ...mutation.before, currency: "EUR", amount_cents: 12345 };
  mutation.after = { ...mutation.after, currency: "INR", amount_cents: 67890 };
  render(<MutationTable mutations={{ inserted: [], deleted: [], updated: [mutation] }} />);
  expect(screen.getByText("EUR 123.45")).toBeTruthy();
  expect(screen.getByText("INR 678.90")).toBeTruthy();
});
