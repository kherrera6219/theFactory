"""Unit tests for Go and Haskell AST structural extractors."""

from pod_worker.go_ast_extractor import extract_go_ast
from pod_worker.haskell_ast_extractor import extract_haskell_ast
from pod_worker.language_extractor import get_extractor


def test_go_ast_extractor_success():
    go_source = """package main

import (
    "fmt"
    "os"
)

type User struct {
    ID   int
    Name string
}

type Processor interface {
    Process() error
}

func NewUser(name string) *User {
    return &User{Name: name}
}

func (u *User) String() string {
    return u.Name
}
"""
    result = extract_go_ast(go_source)
    assert result is not None
    assert result.package == "main"
    assert "fmt" in result.imports
    assert "os" in result.imports
    assert any(s.name == "User" and not s.is_interface for s in result.structs)
    assert any(s.name == "Processor" and s.is_interface for s in result.structs)
    assert any(f.name == "NewUser" for f in result.functions)
    assert any(f.name == "String" and f.receiver == "u *User" for f in result.functions)

    extractor = get_extractor("go")
    extraction = extractor.extract(go_source)
    assert len(extraction.functions) >= 2
    assert len(extraction.classes) >= 2


def test_haskell_ast_extractor_success():
    haskell_source = """module Data.User (User, formatUser) where

import Data.Text (Text)
import qualified Data.Map as Map

data User = User { userId :: Int, userName :: Text }
type UserDict = Map.Map Int User

formatUser :: User -> String
formatUser u = userName u
"""
    result = extract_haskell_ast(haskell_source)
    assert result is not None
    assert result.module_name == "Data.User"
    assert "Data.Text" in result.imports
    assert "Data.Map" in result.imports
    assert any(t.name == "User" and t.kind == "data" for t in result.types)
    assert any(t.name == "UserDict" and t.kind == "type" for t in result.types)
    assert any(f.name == "formatUser" and f.type_signature == "User -> String" for f in result.functions)

    extractor = get_extractor("haskell")
    extraction = extractor.extract(haskell_source)
    assert len(extraction.functions) >= 1
    assert len(extraction.classes) >= 2
