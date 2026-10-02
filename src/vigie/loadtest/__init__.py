"""Load test helpers: safety guard, question sources and pass or fail verdict.

The Locust scenario in ``load/locustfile.py`` stays thin on purpose. Everything that can be
wrong in a way that matters (hitting production too hard, judging a run as green when it
is not) lives here, where it is typed and unit tested without starting Locust.
"""
