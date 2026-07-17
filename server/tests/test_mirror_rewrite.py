# -*- coding: utf-8 -*-
"""미러 import 경로 치환 테스트."""

from scripts.mirror._rewrite import rewrite_mirror_text, should_rewrite_dest


def test_should_rewrite_mobile_src():
    assert should_rewrite_dest("mobile/src/views/foo.vue")
    assert not should_rewrite_dest("server/schemas/foo.py")


def test_rewrite_features_to_views():
    raw = "import X from '@/features/observation/Foo.vue'"
    assert "@/views/observation/Foo.vue" in rewrite_mirror_text(raw)


def test_rewrite_shared_stores():
    raw = "import { useAppStore } from '@/shared/stores/app'"
    assert "@/composables/stores/app" in rewrite_mirror_text(raw)


def test_rewrite_media_url_for_api_mirror():
    raw = "import { resolveMediaUrl } from '@/shared/mediaUrl'"
    assert "@/utils/mediaUrl" in rewrite_mirror_text(raw)
