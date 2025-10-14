import pytest

from core.services.markdown_renderer import render_to_html


@pytest.mark.parametrize(
    'source',
    [
        'x = \\frac{1}{2}',
        '[]y = x^2[/]',
        '~value~is~x$'
    ],
)
def test_math_rendering_preserves_mathjax_markup(source):
    html = render_to_html(source)
    assert 'math' in html
    assert 'x' in html


def test_render_sanitises_script_tags():
    html = render_to_html('<script>alert(1)</script><p>Safe</p>')
    assert 'alert(1)' not in html
    assert '<p>Safe</p>' in html


def test_render_handles_plain_markdown():
    html = render_to_html('# Title\n\n*Item*')
    assert '<h1>' in html
    assert '<em>Item</em>' in html
