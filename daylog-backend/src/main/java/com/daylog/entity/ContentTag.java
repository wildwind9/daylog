package com.daylog.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "content_tag")
@Getter @Setter @NoArgsConstructor
public class ContentTag {

    @EmbeddedId
    private ContentTagId id = new ContentTagId();

    @ManyToOne(fetch = FetchType.LAZY)
    @MapsId("itemId")
    @JoinColumn(name = "item_id")
    private ContentItem contentItem;

    @ManyToOne(fetch = FetchType.LAZY)
    @MapsId("tagId")
    @JoinColumn(name = "tag_id")
    private Tag tag;

    @Enumerated(EnumType.STRING)
    @Column(name = "tag_source", nullable = false, columnDefinition = "varchar(20)")
    private TagSource tagSource;

    public ContentTag(ContentItem contentItem, Tag tag, TagSource tagSource) {
        this.contentItem = contentItem;
        this.tag = tag;
        this.tagSource = tagSource;
        this.id = new ContentTagId(contentItem.getId(), tag.getId());
    }

    public enum TagSource {
        llm, local, manual
    }

    @Embeddable
    @Getter @Setter @NoArgsConstructor
    public static class ContentTagId implements java.io.Serializable {
        @Column(name = "item_id")
        private Long itemId;
        @Column(name = "tag_id")
        private Long tagId;

        public ContentTagId(Long itemId, Long tagId) {
            this.itemId = itemId;
            this.tagId = tagId;
        }
    }
}
