--
-- PostgreSQL database dump
--

-- Dumped from database version 16.3 (Debian 16.3-1.pgdg120+1)
-- Dumped by pg_dump version 16.3 (Debian 16.3-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: context; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.context (id, system, code, version, display) FROM stdin;
\.


--
-- Data for Name: mapping; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.mapping (id, name, type, content) FROM stdin;
\.


--
-- Data for Name: termcode; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.termcode (id, system, code, version, display) FROM stdin;
\.


--
-- Data for Name: ui_profile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ui_profile (id, name, ui_profile) FROM stdin;
\.


--
-- Data for Name: contextualized_termcode; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.contextualized_termcode (context_termcode_hash, context_id, termcode_id, mapping_id, ui_profile_id) FROM stdin;
\.


--
-- Data for Name: criteria_set; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.criteria_set (id, url) FROM stdin;
\.


--
-- Data for Name: contextualized_termcode_to_criteria_set; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.contextualized_termcode_to_criteria_set (context_termcode_hash, criteria_set_id) FROM stdin;
\.


--
-- Name: context_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.context_id_seq', 1, false);


--
-- Name: criteria_set_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.criteria_set_id_seq', 1, false);


--
-- Name: mapping_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.mapping_id_seq', 1, false);


--
-- Name: termcode_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.termcode_id_seq', 1, false);


--
-- Name: ui_profile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ui_profile_id_seq', 1, false);


--
-- PostgreSQL database dump complete
--

