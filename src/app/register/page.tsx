import { AuthPage } from "@/components/site/auth-page";

export const metadata = {
  title: "Create Account — Zemest",
  description: "Create your Zemest account and build your first AI sales agent in less than 5 minutes.",
};

export default function RegisterPage() {
  // Wired to the real register API (POST /api/auth/register → JWT cookie).
  // The previous standalone form only did client-side checks and then
  // redirected to /dashboard without ever creating an account.
  return <AuthPage mode="get-started" />;
}
