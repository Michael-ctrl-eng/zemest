import { AuthPage } from "@/components/site/auth-page";

export const metadata = {
  title: "Login — Zemest",
  description: "Sign in to your Zemest account.",
};

export default function LoginPage() {
  return <AuthPage mode="login" />;
}
