/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2025 Baldur Karlsson
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 ******************************************************************************/

#include "AnnotationDisplay.h"
#include <QAction>
#include <QHeaderView>
#include <QMenu>
#include <QVBoxLayout>

AnnotationDisplay::AnnotationDisplay(ICaptureContext &ctx, bool standalone, QWidget *parent)
    : QFrame(parent), m_Ctx(ctx), m_Standalone(standalone)
{
  m_Tree = new RDTreeWidget(this);

  m_Tree->setColumns({lit("Key"), tr("Value")});
  m_Tree->header()->resizeSection(0, 150);
  m_Tree->setFont(Formatter::PreferredFont());

  QVBoxLayout *layout = new QVBoxLayout(this);
  layout->setSpacing(0);
  layout->setMargin(m_Standalone ? 3 : 0);

  layout->addWidget(m_Tree);

  if(!m_Standalone)
  {
    setFrameStyle(QFrame::NoFrame);
    m_Tree->setFrameStyle(QFrame::NoFrame);
  }

  setWindowTitle(tr("Annotation Viewer"));

  QObject::connect(m_Tree, &RDTreeWidget::customContextMenu, this,
                   &AnnotationDisplay::customContextMenu);

  if(m_Standalone)
    m_Ctx.AddCaptureViewer(this);
}

AnnotationDisplay::~AnnotationDisplay()
{
  if(m_Standalone)
    m_Ctx.RemoveCaptureViewer(this);
}

void AnnotationDisplay::RevealAnnotation(const rdcstr &keyPath)
{
  if(m_Annotation)
  {
    const SDObject *obj = m_Annotation->FindChildByKeyPath(keyPath);

    RDTreeWidgetItem *item = m_Items[obj];
    if(item)
    {
      m_Tree->setSelectedItem(item);
      m_Tree->scrollToItem(item);
    }
  }
}

void AnnotationDisplay::OnCaptureLoaded()
{
  setAnnotationObject(NULL);
}

void AnnotationDisplay::OnCaptureClosed()
{
  setAnnotationObject(NULL);
}

void AnnotationDisplay::OnSelectedEventChanged(uint32_t eventId)
{
  APIEvent ev = m_Ctx.GetEventBrowser()->GetAPIEventForEID(eventId);

  setAnnotationObject(ev.annotations);
}

void AnnotationDisplay::addStructuredChildren(RDTreeWidgetItem *parent, const SDObject &parentObj)
{
  for(const SDObject *obj : parentObj)
  {
    if(obj->type.flags & SDTypeFlags::Hidden)
      continue;

    if(obj->name.beginsWith("__"))
      continue;

    QVariant name;

    if(parentObj.type.basetype == SDBasic::Array)
      name = QFormatStr("[%1]").arg(parent->childCount());
    else
      name = obj->name;

    RDTreeWidgetItem *item = new RDTreeWidgetItem({name, QString()});

    m_Items[obj] = item;
    item->setTag(QVariant::fromValue((void *)obj));

    if(obj->type.basetype == SDBasic::Chunk || obj->type.basetype == SDBasic::Struct ||
       obj->type.basetype == SDBasic::Array)
      addStructuredChildren(item, *obj);
    else
      item->setText(1, SDObject2Variant(obj, false));

    parent->addChild(item);
  }
}

void AnnotationDisplay::setAnnotationObject(const SDObject *annotation)
{
  m_Tree->updateExpansion(m_Expansion, 0);

  m_Annotation = annotation;

  m_Items.clear();
  m_Tree->invisibleRootItem()->clear();

  if(m_Annotation)
  {
    m_Tree->beginUpdate();
    addStructuredChildren(m_Tree->invisibleRootItem(), *m_Annotation);
    m_Tree->endUpdate();
  }

  m_Tree->applyExpansion(m_Expansion, 0);
}

void AnnotationDisplay::customContextMenu(QModelIndex index, QMenu *menu)
{
  RDTreeWidgetItem *item = m_Tree->itemForIndex(index);
  const SDObject *obj = (const SDObject *)item->tag().value<void *>();

  rdcstr path;
  // don't include the root node, it's not part of the path, so only iterate over nodes that have
  // parents themselves
  while(obj && obj->GetParent())
  {
    if(path.empty())
      path = obj->name;
    else
      path = obj->name + rdcstr(".") + path;
    obj = obj->GetParent();
  }

  if(path.empty())
    return;

  QAction *sep = menu->insertSeparator(menu->actions()[0]);

  QAction *showInEventBrowser = new QAction(tr("&Highlight in Event Browser"), menu);

  QObject::connect(showInEventBrowser, &QAction::triggered,
                   [this, path]() { m_Ctx.GetEventBrowser()->SetHighlightedAnnotation(path); });

  menu->insertAction(sep, showInEventBrowser);
}
