import { Navbar } from "@/components/site/navbar";
import { Hero } from "@/components/site/hero";
import { Logos } from "@/components/site/logos";
import { UseCases } from "@/components/site/use-cases";
import { WhatIsPAL } from "@/components/site/what-is-pal";
import { Products } from "@/components/site/products";
import { ConversationalDemo } from "@/components/site/conversational-demo";
import { BuildWithUs } from "@/components/site/build-with-us";
import { CTA } from "@/components/site/cta";
import { Footer } from "@/components/site/footer";

export default function Home() {
  return (
    <div className="relative min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <Logos />
        <UseCases />
        <WhatIsPAL />
        <Products />
        <ConversationalDemo />
        <BuildWithUs />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
