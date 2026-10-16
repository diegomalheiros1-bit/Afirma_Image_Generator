from pathlib import Path
import tempfile
import unicodedata
from support import IsolatedTest, png_bytes
from src.file_manager import validate_reference_paths


class ReferenceLookupTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.products, self.fixed = self.root/'products', self.root/'fixed'
        self.products.mkdir(); self.fixed.mkdir()
        self.roots = {'Produtos': self.products, 'Fixas': self.fixed}
        (self.products/'sachê.jpg').write_bytes(png_bytes())
        (self.fixed/'afeto.jpeg').write_bytes(png_bytes())

    def test_names_search_all_folders_preserving_order_and_unicode_equivalence(self):
        name = unicodedata.normalize('NFD', 'sachê.jpg')
        expected = (self.products/'sachê.jpg', self.fixed/'afeto.jpeg')
        for default in (None, self.products):
            self.assertEqual(validate_reference_paths(default, name+'; afeto.jpeg', self.roots), expected)
        self.assertEqual(validate_reference_paths(None, 'Produtos::'+name, self.roots), expected[:1])

    def test_ambiguous_names_require_alias_even_with_default(self):
        (self.fixed/'sachê.jpg').write_bytes(png_bytes())
        with self.assertRaisesRegex(ValueError, 'mais de uma pasta'):
            validate_reference_paths(self.products, 'sachê.jpg', self.roots)
        self.assertEqual(validate_reference_paths(None, 'Produtos::sachê.jpg', self.roots),
                         (self.products/'sachê.jpg',))

    def test_same_folder_registered_twice_is_not_ambiguous(self):
        roots = {**self.roots, 'Again': self.products}
        self.assertEqual(validate_reference_paths(self.products, 'sachê.jpg', roots),
                         (self.products/'sachê.jpg',))

    def test_extensions_and_accents_are_not_guessed(self):
        for name in ('sache.jpg', 'sachê.jpeg', 'missing.jpg'):
            with self.assertRaises(FileNotFoundError):
                validate_reference_paths(None, name, self.roots)
        with self.assertRaisesRegex(ValueError, 'Extensão'):
            validate_reference_paths(None, 'sachê.gif', self.roots)

    def test_subfolders_normalize_each_component_and_never_escape_root(self):
        folder = self.products/'coleção'
        folder.mkdir()
        (folder/'loção.jpg').write_bytes(png_bytes())
        filename = unicodedata.normalize('NFD', 'coleção/loção.jpg')
        self.assertEqual(validate_reference_paths(None, filename, self.roots), (folder/'loção.jpg',))
        with self.assertRaisesRegex(ValueError, 'fora da pasta'):
            validate_reference_paths(None, '../outside.jpg', self.roots)

    def test_normalized_name_collision_is_not_silently_chosen(self):
        (self.products/unicodedata.normalize('NFD', 'sachê.jpg')).write_bytes(png_bytes())
        with self.assertRaisesRegex(ValueError, 'ambíguo'):
            validate_reference_paths(None, 'sachê.jpg', self.roots)
