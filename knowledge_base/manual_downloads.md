# Manual downloads checklist

The following PDFs cannot be retrieved by `fetch.py` (Cloudflare bot
protection, non-validating TLS chains, etc.). Please open each URL in a
normal web browser, save the file **using the exact target filename**, and
place it inside `knowledge_base/pdfs/`. Then re-run `python fetch.py` - it
will pick the new file up, compute the SHA-256, and mark it OK.

Total pending: **6**

## `B01_ofcom_spectrum_roadmap_2022` - Spectrum Roadmap: Delivering Ofcom's Spectrum Management Strategy

- Publisher: Ofcom (UK) (2022)
- Direct PDF URL: <https://www.ofcom.org.uk/siteassets/resources/documents/consultations/category-2-6-weeks/234683-spectrum-roadmap-delivering-ofcoms-spectrum-management-strategy/associated-documents/spectrum-roadmap.pdf>
- Landing page (if direct link is blocked): <https://www.ofcom.org.uk/spectrum/frequencies/spectrum-management-strategy>
- Save as: `pdfs/B01_ofcom_spectrum_roadmap_2022.pdf`
- Why: Ofcom is behind a Cloudflare bot-challenge that returns HTTP 403 to scripted clients. Open the URL in a normal browser and save the PDF as the target filename into pdfs/.

## `B02_ofcom_space_spectrum_strategy_2017` - Space Spectrum Strategy

- Publisher: Ofcom (UK) (2017)
- Direct PDF URL: <https://www.ofcom.org.uk/siteassets/resources/documents/consultations/uncategorised/7813-space-spectrum-strategy/associated-documents/statement-space-spectrum.pdf>
- Landing page (if direct link is blocked): <https://www.ofcom.org.uk/spectrum/satellite-and-space/space-spectrum-strategy>
- Save as: `pdfs/B02_ofcom_space_spectrum_strategy_2017.pdf`
- Why: Ofcom is behind a Cloudflare bot-challenge that returns HTTP 403 to scripted clients. Open the URL in a normal browser and save the PDF as the target filename into pdfs/.

## `B03_cept_ecc_report_15_enforcement` - ECC Report 15 - Market Surveillance, Radio Equipment Inspection, Interference Investigation, Spectrum Monitoring and the Enforcement Aspects of These Activities

- Publisher: CEPT / ECC (2008)
- Direct PDF URL: <https://docdb.cept.org/download/256>
- Landing page (if direct link is blocked): <https://docdb.cept.org/document/256>
- Save as: `pdfs/B03_cept_ecc_report_15_enforcement.pdf`
- Why: docdb.cept.org presents a TLS certificate chain that Python's CA store (and certifi) does not validate. A normal browser accepts it. Open the URL in a browser and save the PDF as the target filename into pdfs/.

## `B04_cept_ecc_rec_05_01_automated_monitoring` - ECC Recommendation (05)01 - Harmonisation of Automatic Measuring Methods and Data Transfer for Frequency Band Registrations

- Publisher: CEPT / ECC (2018)
- Direct PDF URL: <https://docdb.cept.org/download/1862>
- Landing page (if direct link is blocked): <https://docdb.cept.org/document/1862>
- Save as: `pdfs/B04_cept_ecc_rec_05_01_automated_monitoring.pdf`
- Why: docdb.cept.org TLS chain not validated by Python/certifi. Open in a browser and save as the target filename into pdfs/.

## `B05_cept_ecc_report_160_benchmarking` - ECC Report 160 - Enforcement Benchmarking in the Year 2010

- Publisher: CEPT / ECC (2011)
- Direct PDF URL: <https://docdb.cept.org/download/633>
- Landing page (if direct link is blocked): <https://docdb.cept.org/document/633>
- Save as: `pdfs/B05_cept_ecc_report_160_benchmarking.pdf`
- Why: docdb.cept.org TLS chain not validated by Python/certifi. Open in a browser and save as the target filename into pdfs/.

## `J03_rs_whitepaper_intro_direction_finding_methodologies` - An Introduction to Direction Finding Methodologies - White Paper

- Publisher: Rohde & Schwarz (2020)
- Direct PDF URL: <https://cdn.rohde-schwarz.com/am/us/campaigns_2/a_d/Intro-to-direction-finding-methodologies~1.pdf>
- Landing page (if direct link is blocked): <https://www.rohde-schwarz.com/us/campaigns/gov/direction-finding_252649.html>
- Save as: `pdfs/J03_rs_whitepaper_intro_direction_finding_methodologies.pdf`
- Why: The previously direct CDN URL now returns 404. The whitepaper is still linked from the Direction Finding Resources landing page (see landing_page). Open it there, download the current PDF and save with the target filename in pdfs/.

