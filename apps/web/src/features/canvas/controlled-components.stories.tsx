import { Badge, Button, Card, Input, type ButtonProps } from "@itl/design-system";
import type { Meta, StoryObj } from "@storybook/react";

const buttonMeta = {
  component: Button,
  title: "Controlled UI/Button",
} satisfies Meta<typeof Button>;

export default buttonMeta;

type ButtonStory = StoryObj<typeof buttonMeta>;

const baseButton: ButtonProps = {
  background: "accent",
  border: "none",
  density: "comfortable",
  fontWeight: "semibold",
  foreground: "light",
  label: "Continue",
  radius: "soft",
  size: "regular",
  state: "default",
  variant: "solid",
};

export const TechnicalSquare: ButtonStory = {
  args: { ...baseButton, radius: "square" },
};

export const Subtle: ButtonStory = {
  args: { ...baseButton, background: "surface", border: "none", foreground: "dark", variant: "subtle" },
};

export const Outline: ButtonStory = {
  args: { ...baseButton, background: "transparent", border: "strong", foreground: "dark", variant: "outline" },
};

export const Compact: ButtonStory = {
  args: { ...baseButton, density: "compact", size: "compact" },
};

export const Disabled: ButtonStory = {
  args: { ...baseButton, state: "disabled" },
};

export const Loading: ButtonStory = {
  args: { ...baseButton, state: "loading" },
};

export const FocusVisible: ButtonStory = {
  args: { ...baseButton, label: "Tab to inspect focus" },
  play: async ({ canvas }) => {
    canvas.getByRole("button").focus();
  },
};

export const RegisteredAtoms: StoryObj = {
  render: () => (
    <Card description="The catalog registry uses these shared components." emphasis="raised" title="Registered atoms">
      <Badge label="Ready" tone="success" />
      <Input label="Name" placeholder="Ada Lovelace" state="default" tone="quiet" value="" />
    </Card>
  ),
};
